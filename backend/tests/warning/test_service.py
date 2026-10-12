"""Chạy cảnh báo cho lớp trên dữ liệu seed: học sinh biên, lưu kiểu thêm-khi-đổi, hook (D-071).

Học sinh biên của seed: HS1102001 (11A2, nghỉ 38 buổi), HS1102002 (11A2, Toán 3,0),
HS1201001/2/3 (12A1, nghỉ 44, 45, 46), HS1201004/5/6 (12A1, Toán đúng 3,4 / 3,5 / 5,0).
"""

import logging
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.classes.academic import Attendance
from app.classes.models import ClassStudent, Student
from app.core.enums import RiskLevel, TeacherStatus
from app.imports import hooks
from app.warning import repository as repo
from app.warning import service
from app.warning.models import RiskAlert
from tests.conftest import _BorrowedSession

pytestmark = pytest.mark.db

ClassId = Callable[[str], int]


@pytest.fixture
def current(db_session: Session) -> Callable[[str], RiskAlert]:
    """Cảnh báo hiện hành (dòng mới nhất) của một học sinh theo mã."""

    def find(code: str) -> RiskAlert:
        cs_id = db_session.scalar(
            select(ClassStudent.id)
            .join(Student, Student.id == ClassStudent.student_id)
            .where(Student.student_code == code)
        )
        assert cs_id is not None, code
        alert = repo.current_for_student(db_session, cs_id)
        assert alert is not None, f"{code} chưa có cảnh báo"
        return alert

    return find


def rule_codes(alert: RiskAlert) -> list[str]:
    return [rule["code"] for rule in alert.reasons["rules"]]


def row_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(RiskAlert)) or 0


def test_refresh_gives_every_student_of_the_class_one_current_alert(
    db_session: Session, class_id_of: ClassId
) -> None:
    result = service.refresh_class(db_session, class_id_of("11A2"))

    assert (result.inserted, result.unchanged) == (40, 0)
    assert sum(result.counts.values()) == 40
    assert row_count(db_session) == 40


def test_demo_students_of_class_11a2(
    db_session: Session, class_id_of: ClassId, current: Callable[[str], RiskAlert]
) -> None:
    service.refresh_class(db_session, class_id_of("11A2"))

    an = current("HS1102001")  # nghỉ 38 buổi: nhắc, chưa phải mức cao
    assert an.level is RiskLevel.MEDIUM and "absent_notice" in rule_codes(an)
    assert any("38 buổi" in rule["message"] for rule in an.reasons["rules"])
    toan_3 = current("HS1102002")  # mọi đầu điểm Toán bằng 3,0
    assert toan_3.level is RiskLevel.HIGH
    assert {"subject_below_fail", "level_fail"} <= set(rule_codes(toan_3))
    assert an.risk_score is None and an.model_version is None  # chưa có mô hình ML ở bước này


def test_boundary_students_of_class_12a1(
    db_session: Session, class_id_of: ClassId, current: Callable[[str], RiskAlert]
) -> None:
    service.refresh_class(db_session, class_id_of("12A1"))

    # Nghỉ 44 và 45 buổi: mức cao nhưng chưa vượt; 46 buổi: vượt mức tối đa.
    assert "absent_high" in rule_codes(current("HS1201001"))
    assert "absent_high" in rule_codes(current("HS1201002"))
    assert "absent_over_limit" in rule_codes(current("HS1201003"))
    assert "absent_over_limit" not in rule_codes(current("HS1201002"))
    for code in ("HS1201001", "HS1201002", "HS1201003"):
        assert current(code).level is RiskLevel.HIGH
    # Toán đúng 3,4 dưới 3,5; đúng 3,5 thì không; đúng 5,0 thì cũng không bị gì ở môn đó.
    assert "subject_below_fail" in rule_codes(current("HS1201004"))
    assert "subject_below_fail" not in rule_codes(current("HS1201005"))
    assert "subject_below_fail" not in rule_codes(current("HS1201006"))
    low_toan = [
        r for r in current("HS1201004").reasons["rules"] if r["code"] == "subject_below_fail"
    ]
    assert "Toán (3,4)" in low_toan[0]["message"]


def test_grade_12_exam_subjects_are_checked_and_other_grades_are_not(
    db_session: Session, class_id_of: ClassId
) -> None:
    service.refresh_class(db_session, class_id_of("12A1"))
    service.refresh_class(db_session, class_id_of("11A2"))

    rows = repo.current_alerts(db_session)
    exam = [r for r in rows if "grade12_exam_low" in rule_codes(r.alert)]
    assert exam and all(r.class_name.startswith("12") for r in exam)


def test_running_again_with_the_same_data_adds_no_rows(
    db_session: Session, class_id_of: ClassId
) -> None:
    class_id = class_id_of("11A2")
    service.refresh_class(db_session, class_id)
    before = row_count(db_session)

    again = service.refresh_class(db_session, class_id)

    assert (again.inserted, again.unchanged) == (0, 40)
    assert row_count(db_session) == before


def test_the_teachers_note_survives_a_rerun_and_a_change_adds_a_new_row(
    db_session: Session, class_id_of: ClassId, current: Callable[[str], RiskAlert]
) -> None:
    class_id = class_id_of("11A2")
    service.refresh_class(db_session, class_id)
    first = current("HS1102001")
    first.teacher_status = TeacherStatus.CONTACTED
    db_session.flush()

    service.refresh_class(db_session, class_id)  # cùng dữ liệu
    assert current("HS1102001").id == first.id
    assert current("HS1102001").teacher_status is TeacherStatus.CONTACTED  # không bị mất

    # Đổi dữ liệu: xoá hết điểm danh của em An, số buổi nghỉ về 0 nên cảnh báo đổi.
    cs_id = first.class_student_id
    db_session.execute(delete(Attendance).where(Attendance.class_student_id == cs_id))
    result = service.refresh_class(db_session, class_id)

    assert result.inserted == 1
    newest = current("HS1102001")
    assert newest.id != first.id and newest.level is RiskLevel.LOW
    assert newest.teacher_status is TeacherStatus.NEW  # cảnh báo mới chưa được ghi nhận
    db_session.refresh(first)
    assert first.teacher_status is TeacherStatus.CONTACTED  # dòng cũ giữ nguyên (lịch sử)
    assert "absent_notice" in rule_codes(first)  # lý do của dòng cũ còn nguyên


def test_alerts_hold_no_name_and_no_guardian_data(
    db_session: Session, class_id_of: ClassId
) -> None:
    service.refresh_class(db_session, class_id_of("11A2"))

    text = " ".join(str(alert.reasons) for alert in db_session.scalars(select(RiskAlert)))
    names = db_session.scalars(select(Student.full_name).limit(400)).all()
    assert not any(name in text for name in names)
    assert "guardian" not in text and "date_of_birth" not in text


def test_unknown_class_is_a_lookup_error(db_session: Session) -> None:
    with pytest.raises(LookupError):
        service.refresh_class(db_session, 999999)


# --- Hook on_data_changed ----------------------------------------------------------------------


def test_the_import_hook_runs_the_class_warning_in_its_own_session(
    db_session: Session, class_id_of: ClassId, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hooks, "get_session_factory", lambda: lambda: _BorrowedSession(db_session))
    assert row_count(db_session) == 0

    hooks.on_data_changed(class_id_of("11A2"))

    assert row_count(db_session) == 40


def test_a_failure_in_the_warning_never_breaks_the_import_hook(
    db_session: Session,
    class_id_of: ClassId,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("lỗi giả lập khi chạy cảnh báo")

    monkeypatch.setattr(hooks, "get_session_factory", lambda: lambda: _BorrowedSession(db_session))
    monkeypatch.setattr(service, "refresh_class", boom)

    with caplog.at_level(logging.ERROR, logger="app.warning.service"):
        hooks.on_data_changed(class_id_of("11A2"))  # không ném lỗi ra ngoài

    assert any("cảnh báo sớm" in record.getMessage() for record in caplog.records)
    assert row_count(db_session) == 0

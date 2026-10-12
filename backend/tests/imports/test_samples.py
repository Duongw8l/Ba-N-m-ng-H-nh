"""Ba tệp mẫu trong data/samples/: khớp bộ sinh, và chạy được qua đúng kịch bản demo (DESIGN 12)."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.analytics.config import load_config
from app.classes.academic import Attendance
from app.classes.models import ClassStudent
from app.imports.parsing import read_grid
from data.samples import build
from tests.imports.conftest import ImportApi

pytestmark = pytest.mark.db

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "data" / "samples"
TOAN_TEACHER = "gv.toan.11@example.com"
HOMEROOM_11A2 = "gvcn.11a2@example.com"


def sample_bytes(name: str) -> bytes:
    return (SAMPLES_DIR / name).read_bytes()


def test_committed_samples_are_what_the_generator_produces_now(db_session: Session) -> None:
    """Đổi seed mà quên chạy lại `make samples` thì test này báo (so nội dung, không so byte)."""
    fresh = build.build_samples(load_config(db_session))

    assert set(fresh) == {build.CORRECT_XLSX, build.FAULTY_XLSX, build.ATTENDANCE_CSV}
    for name, content in fresh.items():
        assert read_grid(name, sample_bytes(name)) == read_grid(name, content), name


def test_average_column_of_the_correct_sample_matches_a_hand_computation() -> None:
    """ĐTB = (tổng tx + 2×gk + 3×ck) / (số tx + 5), làm tròn nửa lên 1 chữ số (Thông tư 22)."""
    grid = read_grid(build.CORRECT_XLSX, sample_bytes(build.CORRECT_XLSX))

    students = grid[build.FIRST_DATA_LINE - 1 :]
    assert len(students) == 40
    for row in students:
        tx = [Decimal(cell) for cell in row[3:7]]
        gk, ck, shown = Decimal(row[7]), Decimal(row[8]), Decimal(row[9])
        expected = ((sum(tx) + 2 * gk + 3 * ck) / 9).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
        assert shown == expected, row[1]


def test_correct_sample_previews_with_three_changes_then_imports(imp: ImportApi) -> None:
    before = imp.score_snapshot()
    response = imp.upload(
        TOAN_TEACHER,
        "11A2",
        "assessments",
        sample_bytes(build.CORRECT_XLSX),
        build.CORRECT_XLSX,
        subject_id=imp.subject_id_of("Toán"),
        semester=1,
    )

    body = response.json()
    assert response.status_code == 200, response.text
    assert body["header_line"] == build.HEADER_LINE
    assert body["missing_required"] == [] and body["ignored_columns"] == ["STT", "ĐTB"]
    assert {f["name"]: f["column"] for f in body["fields"]}["midterm"] == "ĐĐGgk"
    assert body["summary"]["error_rows"] == 0 and body["summary"]["warning_rows"] == 0
    assert (body["summary"]["changed_rows"], body["summary"]["unchanged_rows"]) == (3, 37)
    assert imp.score_snapshot() == before

    result = imp.confirm(TOAN_TEACHER, body["job_id"]).json()
    assert (result["created"], result["updated"]) == (0, 3)
    after = imp.score_snapshot()
    assert sum(1 for key in after if after[key] != before[key]) == 3
    assert all(abs(after[k] - before[k]) == Decimal("0.5") for k in after if after[k] != before[k])


def test_faulty_sample_reports_each_planted_fault_on_its_own_line(imp: ImportApi) -> None:
    before = imp.score_snapshot()
    response = imp.upload(
        TOAN_TEACHER,
        "11A2",
        "assessments",
        sample_bytes(build.FAULTY_XLSX),
        build.FAULTY_XLSX,
        subject_id=imp.subject_id_of("Toán"),
        semester=1,
    )

    body = response.json()
    assert response.status_code == 200, response.text
    rows = {row["line"]: row for row in body["rows"]}
    for fault in build.FAULTS:
        row = rows[fault.line]
        assert row["status"] == fault.severity, fault
        [message] = row["messages"]
        assert message["column"] == fault.column and fault.fragment in message["message"], fault
    planted_errors = [f for f in build.FAULTS if f.severity == "error"]
    assert body["summary"]["error_rows"] == len(planted_errors) == 6
    assert body["summary"]["warning_rows"] == 1
    # Dòng dùng dấu phẩy ("7,5") hợp lệ: không lỗi, không cảnh báo, không đổi gì so với DB.
    comma = rows.get(build.FIRST_DATA_LINE + build.COMMA_STUDENT)
    assert comma is None or (comma["status"] == "ok" and comma["action"] == "unchanged")
    assert body["can_confirm"] is False

    assert imp.confirm(TOAN_TEACHER, body["job_id"]).status_code == 422
    assert imp.score_snapshot() == before  # cả các dòng hợp lệ cũng không được ghi


def upload_attendance(imp: ImportApi) -> dict:
    response = imp.upload(
        HOMEROOM_11A2,
        "11A2",
        "attendance",
        sample_bytes(build.ATTENDANCE_CSV),
        build.ATTENDANCE_CSV,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_attendance_sample_matches_the_default_seed_exactly(imp: ImportApi) -> None:
    body = upload_attendance(imp)

    assert body["summary"]["total_rows"] == 40 * 23  # 40 học sinh × 23 ngày học tháng 3/2027
    assert body["summary"]["error_rows"] == 0
    assert body["summary"]["unchanged_rows"] == 40 * 23  # DB mặc định đã có đúng dữ liệu này
    assert body["summary"]["has_changes"] is False


def test_demo_scenario_hold_out_then_import_restores_the_full_year(imp: ImportApi) -> None:
    """Giống `make seed SEED_ARGS="--hold-out 2027-03"` rồi nhập tệp mẫu: ra đúng dữ liệu seed."""
    full_year = imp.attendance_snapshot()
    march = {key for key in full_year if (key[1].year, key[1].month) == (2027, 3)}
    assert len(march) == 40 * 23
    imp.session.execute(
        delete(Attendance).where(
            Attendance.date >= date(2027, 3, 1),
            Attendance.date < date(2027, 4, 1),
            Attendance.class_student_id.in_(
                ClassStudent.__table__.select()
                .with_only_columns(ClassStudent.id)
                .where(ClassStudent.class_id == imp.class_id_of("11A2"))
            ),
        )
    )
    assert len(imp.attendance_snapshot()) == len(full_year) - len(march)

    body = upload_attendance(imp)
    assert body["summary"]["new_rows"] == 40 * 23  # tháng 3 là dữ liệu MỚI
    assert body["summary"]["unchanged_rows"] == 0

    result = imp.confirm(HOMEROOM_11A2, body["job_id"]).json()
    assert result["created"] == 40 * 23
    assert imp.attendance_snapshot() == full_year  # y hệt seed đầy đủ

    again = upload_attendance(imp)  # nhập lại lần nữa: không có gì mới
    assert again["summary"]["new_rows"] == 0 and again["summary"]["unchanged_rows"] == 40 * 23

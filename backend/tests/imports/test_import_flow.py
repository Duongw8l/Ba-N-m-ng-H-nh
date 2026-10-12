"""Luồng nhập tệp trên DB thật: xem trước không ghi, xác nhận mới ghi, tất cả hoặc không gì (D-059).

Tài khoản (README): gv.toan.11 dạy Toán 11A1-11A3 và chủ nhiệm 11A1; gvcn.11a2 chủ nhiệm 11A2;
gv.gdtc.11 dạy Giáo dục thể chất (môn nhận xét) khối 11; gv.van.11 dạy Văn khối 11.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from app.auth.models import AuditLog
from app.classes.academic import Assessment, Attendance
from app.classes.models import ClassStudent, Student
from app.core.enums import AuditAction
from app.imports.models import ImportJob
from app.warning.models import RiskAlert
from tests.imports.conftest import ImportApi, ScoreSheet, build_csv, build_xlsx

pytestmark = pytest.mark.db

TOAN_TEACHER = "gv.toan.11@example.com"
HOMEROOM_11A2 = "gvcn.11a2@example.com"
GDTC_TEACHER = "gv.gdtc.11@example.com"


def other_score(value: float) -> float:
    return 9.0 if value != 9.0 else 8.0


def count(imp: ImportApi, model: Any) -> int:
    return imp.session.scalar(select(func.count()).select_from(model)) or 0


def import_audits(imp: ImportApi) -> list[AuditLog]:
    return list(
        imp.session.scalars(select(AuditLog).where(AuditLog.action == AuditAction.IMPORT_CONFIRM))
    )


# --- Xem trước không ghi gì ---------------------------------------------------------------------


def test_a_file_identical_to_the_database_previews_as_all_unchanged(imp: ImportApi) -> None:
    sheet = imp.score_sheet()
    before = imp.score_snapshot()

    response = imp.upload_scores(TOAN_TEACHER, sheet)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"]["error_rows"] == 0
    assert body["summary"]["total_rows"] == 40
    assert body["summary"]["unchanged_rows"] == 40
    assert body["summary"]["records_unchanged"] == len(before) == 40 * (sheet.tx_count + 2)
    assert body["summary"]["has_changes"] is False
    assert body["can_confirm"] is True and body["job_id"]
    assert body["header_line"] == 1
    assert body["ignored_columns"] == ["STT", "ĐTB"]
    assert body["subject"]["name"] == "Toán" and body["semester"] == 1
    assert imp.score_snapshot() == before  # xem trước không ghi gì


def test_preview_shows_old_and_new_value_of_a_changed_score(imp: ImportApi) -> None:
    sheet = imp.score_sheet()
    code = sheet.rows[5][1]
    old = sheet.rows[5][sheet.column("TX2")]
    sheet.rows[5][sheet.column("TX2")] = other_score(old)

    body = imp.upload_scores(TOAN_TEACHER, sheet).json()

    assert body["summary"]["changed_rows"] == 1 and body["summary"]["unchanged_rows"] == 39
    assert body["summary"]["records_to_update"] == 1
    [changed] = [r for r in body["rows"] if r["action"] == "changed"]
    assert changed["student_code"] == code and changed["line"] == 7  # tiêu đề ở dòng 1
    assert changed["existing"] == {"tx2": f"{Decimal(str(old)):.1f}"}
    assert changed["values"]["tx2"] == f"{other_score(old):.1f}"


def test_title_rows_above_the_header_are_skipped_and_lines_still_match_the_file(
    imp: ImportApi,
) -> None:
    sheet = imp.score_sheet()
    sheet.rows[0][sheet.column("CK")] = 11  # lỗi ở học sinh đầu tiên

    response = imp.upload(
        TOAN_TEACHER,
        "11A2",
        "assessments",
        sheet.to_xlsx(title_rows=3),
        subject_id=imp.subject_id_of("Toán"),
        semester=1,
    )

    body = response.json()
    assert body["header_line"] == 4
    [bad] = [r for r in body["rows"] if r["status"] == "error"]
    assert bad["line"] == 5  # tiêu đề dòng 4 nên học sinh đầu ở dòng 5
    assert bad["messages"][0]["column"] == "CK"


def test_names_in_the_file_are_never_stored_in_the_job(imp: ImportApi) -> None:
    sheet = imp.score_sheet()
    sheet.rows[0][sheet.column("TX1")] = 7.0

    job_id = imp.upload_scores(TOAN_TEACHER, sheet).json()["job_id"]

    job = imp.session.get(ImportJob, job_id)
    assert job is not None
    stored = str(job.rows) + str(job.summary) + str(job.mapping)
    names = imp.session.scalars(select(Student.full_name).limit(400)).all()
    assert not any(name in stored for name in names)


# --- Xác nhận ghi đúng những gì đã xem ----------------------------------------------------------


def test_confirm_writes_only_the_changed_cell(
    imp: ImportApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = imp.score_sheet()
    code = sheet.rows[3][1]
    old = sheet.rows[3][sheet.column("GK")]
    sheet.rows[3][sheet.column("GK")] = other_score(old)
    before = imp.score_snapshot()
    job_id = imp.upload_scores(TOAN_TEACHER, sheet).json()["job_id"]

    response = imp.confirm(TOAN_TEACHER, job_id)

    assert response.status_code == 200, response.text
    assert response.json() | {"job_id": None} == {
        "job_id": None,
        "status": "confirmed",
        "created": 0,
        "updated": 1,
        "unchanged": len(before) - 1,
        "already_confirmed": False,
    }
    after = imp.score_snapshot()
    differing = {key for key in after if after[key] != before[key]}
    assert differing == {(code, "gk", 1)}
    assert after[(code, "gk", 1)] == Decimal(str(other_score(old)))
    assert len(after) == len(before)  # không thêm dòng nào


def test_importing_the_same_file_again_changes_and_duplicates_nothing(imp: ImportApi) -> None:
    sheet = imp.score_sheet()
    sheet.rows[0][sheet.column("TX1")] = other_score(sheet.rows[0][sheet.column("TX1")])
    first = imp.upload_scores(TOAN_TEACHER, sheet).json()
    imp.confirm(TOAN_TEACHER, first["job_id"])
    rows_before = count(imp, Assessment)
    after_first = imp.score_snapshot()

    second = imp.upload_scores(TOAN_TEACHER, sheet).json()

    assert second["summary"]["changed_rows"] == 0 and second["summary"]["new_rows"] == 0
    assert second["summary"]["unchanged_rows"] == 40
    result = imp.confirm(TOAN_TEACHER, second["job_id"]).json()
    assert (result["created"], result["updated"]) == (0, 0)
    assert count(imp, Assessment) == rows_before
    assert imp.score_snapshot() == after_first


def test_missing_scores_are_created_as_new_records(imp: ImportApi) -> None:
    sheet = imp.score_sheet()
    code = sheet.rows[7][1]
    before = imp.score_snapshot()
    imp.session.execute(
        delete(Assessment).where(
            Assessment.subject_id == imp.subject_id_of("Toán"),
            Assessment.semester == 1,
            Assessment.class_student_id.in_(
                select(ClassStudent.id)
                .join(Student, Student.id == ClassStudent.student_id)
                .where(Student.student_code == code)
            ),
        )
    )
    assert len(imp.score_snapshot()) == len(before) - (sheet.tx_count + 2)

    preview = imp.upload_scores(TOAN_TEACHER, sheet).json()

    assert preview["summary"]["new_rows"] == 1
    assert preview["summary"]["records_to_create"] == sheet.tx_count + 2
    result = imp.confirm(TOAN_TEACHER, preview["job_id"]).json()
    assert (result["created"], result["updated"]) == (sheet.tx_count + 2, 0)
    assert imp.score_snapshot() == before


def test_confirming_twice_writes_once_and_returns_the_same_result(
    imp: ImportApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = imp.score_sheet()
    sheet.rows[0][sheet.column("CK")] = other_score(sheet.rows[0][sheet.column("CK")])
    job_id = imp.upload_scores(TOAN_TEACHER, sheet).json()["job_id"]
    calls: list[int] = []
    monkeypatch.setattr("app.imports.hooks.on_data_changed", calls.append)

    first = imp.confirm(TOAN_TEACHER, job_id).json()
    second = imp.confirm(TOAN_TEACHER, job_id).json()

    assert first["already_confirmed"] is False and second["already_confirmed"] is True
    assert (first["created"], first["updated"]) == (second["created"], second["updated"]) == (0, 1)
    assert len(import_audits(imp)) == 1
    assert calls == [imp.class_id_of("11A2")]  # hook chỉ chạy một lần


def test_confirm_writes_one_audit_row_with_the_numbers(imp: ImportApi) -> None:
    sheet = imp.score_sheet()
    sheet.rows[1][sheet.column("TX1")] = other_score(sheet.rows[1][sheet.column("TX1")])
    job_id = imp.upload_scores(TOAN_TEACHER, sheet).json()["job_id"]
    assert import_audits(imp) == []  # xem trước không ghi nhật ký

    imp.confirm(TOAN_TEACHER, job_id)

    [log] = import_audits(imp)
    assert log.class_id == imp.class_id_of("11A2")
    assert log.details["job_id"] == job_id
    assert log.details["kind"] == "assessments"
    assert (log.details["created"], log.details["updated"]) == (0, 1)
    assert log.details["subject_id"] == imp.subject_id_of("Toán") and log.details["semester"] == 1
    assert "Nguyễn" not in str(log.details)  # không có tên học sinh trong nhật ký


def test_hook_runs_after_the_commit_and_only_when_data_changed(
    imp: ImportApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    real_commit = imp.session.commit

    def commit() -> None:
        real_commit()
        events.append("commit")

    changed = imp.score_sheet()
    changed.rows[0][changed.column("TX1")] = other_score(changed.rows[0][changed.column("TX1")])
    changed_job = imp.upload_scores(TOAN_TEACHER, changed).json()["job_id"]
    same_job = imp.upload_scores(TOAN_TEACHER, imp.score_sheet()).json()["job_id"]
    monkeypatch.setattr(imp.session, "commit", commit)
    monkeypatch.setattr("app.imports.hooks.on_data_changed", lambda class_id: events.append("hook"))

    imp.confirm(TOAN_TEACHER, changed_job)
    assert events == ["commit", "hook"]

    events.clear()
    imp.confirm(TOAN_TEACHER, same_job)  # không có gì đổi: ghi nhận xong nhưng không báo hook
    assert events == ["commit"]


# --- Cảnh báo sớm sau khi nhập (D-071) ---------------------------------------------------------


def test_confirm_runs_the_early_warning_for_the_class(imp: ImportApi) -> None:
    sheet = imp.score_sheet()
    sheet.rows[0][sheet.column("TX1")] = other_score(sheet.rows[0][sheet.column("TX1")])
    job_id = imp.upload_scores(TOAN_TEACHER, sheet).json()["job_id"]
    assert count(imp, RiskAlert) == 0

    response = imp.confirm(TOAN_TEACHER, job_id)

    assert response.status_code == 200
    assert count(imp, RiskAlert) == 40  # mỗi học sinh của 11A2 có một cảnh báo hiện hành


def test_a_failing_warning_does_not_fail_the_confirm(
    imp: ImportApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.warning import service

    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("lỗi giả lập")

    monkeypatch.setattr(service, "refresh_class", boom)
    sheet = imp.score_sheet()
    code = sheet.rows[2][1]
    old = sheet.rows[2][sheet.column("GK")]
    sheet.rows[2][sheet.column("GK")] = other_score(old)
    job_id = imp.upload_scores(TOAN_TEACHER, sheet).json()["job_id"]

    response = imp.confirm(TOAN_TEACHER, job_id)

    assert response.status_code == 200 and response.json()["updated"] == 1
    assert imp.score_snapshot()[(code, "gk", 1)] == Decimal(str(other_score(old)))  # đã ghi
    assert count(imp, RiskAlert) == 0


# --- File lỗi: không ghi gì ---------------------------------------------------------------------


def broken_sheet(imp: ImportApi) -> tuple[ScoreSheet, dict[int, str]]:
    sheet = imp.score_sheet()
    tx1, tx2, gk, ck = (sheet.column(name) for name in ("TX1", "TX2", "GK", "CK"))
    sheet.rows[1][1] = "HS9999999"  # dòng 3: mã không có trong lớp
    sheet.rows[2][gk] = 11  # dòng 4: điểm lớn hơn 10
    sheet.rows[3][tx1] = "tám"  # dòng 5: không phải số
    sheet.rows[4][1] = sheet.rows[0][1]  # dòng 6: trùng mã với dòng 2
    sheet.rows[4][2] = sheet.rows[0][2]  # cùng họ tên để chỉ còn đúng một lỗi
    sheet.rows[5][ck] = None  # dòng 7: thiếu điểm cuối kỳ
    sheet.rows[6][tx2] = "7,25"  # dòng 8: 2 chữ số thập phân
    return sheet, {3: "Mã HS", 4: "GK", 5: "TX1", 6: "Mã HS", 7: "CK", 8: "TX2"}


def test_a_file_with_errors_reports_each_line_and_column(imp: ImportApi) -> None:
    sheet, expected_columns = broken_sheet(imp)

    body = imp.upload_scores(TOAN_TEACHER, sheet).json()

    assert body["summary"]["error_rows"] == 6
    assert body["can_confirm"] is False
    errors = {r["line"]: r for r in body["rows"] if r["status"] == "error"}
    assert set(errors) == set(expected_columns)
    for line, column in expected_columns.items():
        assert [m["column"] for m in errors[line]["messages"]] == [column], line
    assert "không có trong lớp" in errors[3]["messages"][0]["message"]
    assert "khoảng từ 0 đến 10" in errors[4]["messages"][0]["message"]
    assert "không phải là số" in errors[5]["messages"][0]["message"]
    assert "trùng với dòng 2" in errors[6]["messages"][0]["message"]
    assert "Thiếu" in errors[7]["messages"][0]["message"]
    assert "1 chữ số thập phân" in errors[8]["messages"][0]["message"]


def test_confirming_a_file_with_errors_is_refused_and_writes_nothing(
    imp: ImportApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet, _ = broken_sheet(imp)
    sheet.rows[10][sheet.column("TX1")] = other_score(sheet.rows[10][sheet.column("TX1")])
    before = imp.score_snapshot()
    body = imp.upload_scores(TOAN_TEACHER, sheet).json()
    calls: list[int] = []
    monkeypatch.setattr("app.imports.hooks.on_data_changed", calls.append)

    response = imp.confirm(TOAN_TEACHER, body["job_id"])

    assert response.status_code == 422
    assert imp.score_snapshot() == before  # cả dòng hợp lệ cũng không được ghi
    assert import_audits(imp) == [] and calls == []
    job = imp.session.get(ImportJob, body["job_id"])
    assert job is not None and job.rows == [] and job.status.value == "previewed"


def test_a_failure_in_the_middle_of_writing_rolls_everything_back(
    imp: ImportApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = imp.score_sheet()
    for index in (0, 1, 2):
        cell = sheet.column("TX1")
        sheet.rows[index][cell] = other_score(sheet.rows[index][cell])
    before = imp.score_snapshot()
    job_id = imp.upload_scores(TOAN_TEACHER, sheet).json()["job_id"]
    from app.imports import service

    real_write = service.write_job

    def write_then_fail(session: Any, job: Any) -> tuple[int, int]:
        real_write(session, job)  # đã ghi xong rồi mới lỗi: phải hoàn tác hết
        raise IntegrityError("INSERT", {}, Exception("lỗi giả lập giữa chừng"))

    monkeypatch.setattr(service, "write_job", write_then_fail)
    calls: list[int] = []
    monkeypatch.setattr("app.imports.hooks.on_data_changed", calls.append)

    response = imp.confirm(TOAN_TEACHER, job_id)

    assert response.status_code == 409
    assert imp.score_snapshot() == before
    assert import_audits(imp) == [] and calls == []
    job = imp.session.get(ImportJob, job_id)
    assert job is not None and job.status.value == "previewed"


# --- allow_partial và ô trống -------------------------------------------------------------------


def test_missing_score_is_an_error_unless_allow_partial(imp: ImportApi) -> None:
    sheet = imp.score_sheet()
    sheet.rows[2][sheet.column("TX3")] = None

    strict = imp.upload_scores(TOAN_TEACHER, sheet).json()
    partial = imp.upload_scores(TOAN_TEACHER, sheet, allow_partial=True).json()

    assert strict["summary"]["error_rows"] == 1 and strict["can_confirm"] is False
    assert partial["summary"]["error_rows"] == 0 and partial["summary"]["warning_rows"] == 1
    assert partial["can_confirm"] is True


def test_blank_cell_never_clears_a_stored_score(imp: ImportApi) -> None:
    sheet = imp.score_sheet()
    code = sheet.rows[2][1]
    sheet.rows[2][sheet.column("TX3")] = None
    before = imp.score_snapshot()
    stored = before[(code, "tx", 3)]
    assert stored is not None

    preview = imp.upload_scores(TOAN_TEACHER, sheet, allow_partial=True).json()
    result = imp.confirm(TOAN_TEACHER, preview["job_id"]).json()

    assert (result["created"], result["updated"]) == (0, 0)
    assert imp.score_snapshot() == before
    assert imp.score_snapshot()[(code, "tx", 3)] == stored


def test_comma_decimals_and_a_wrong_name_are_accepted_with_a_warning(imp: ImportApi) -> None:
    sheet = imp.score_sheet()
    sheet.rows[0][sheet.column("TX1")] = "7,5"
    sheet.rows[1][2] = "Một Cái Tên Khác"

    body = imp.upload_scores(TOAN_TEACHER, sheet).json()

    assert body["summary"]["error_rows"] == 0 and body["summary"]["warning_rows"] == 1
    assert body["can_confirm"] is True
    [warned] = [r for r in body["rows"] if r["status"] == "warning"]
    assert warned["messages"][0]["column"] == "Họ và tên"
    comma = next(r for r in body["rows"] if r["line"] == 2)
    assert comma["values"]["tx1"] == "7.5"


# --- Cột thiếu và mẫu ánh xạ --------------------------------------------------------------------

ODD_HEADERS = ["Số hiệu", "Tên", "Lần 1", "Lần 2", "Lần 3", "Lần 4", "Giữa HK", "Cuối HK"]
ODD_MAPPING = {
    "student_code": "Số hiệu",
    "full_name": "Tên",
    "tx1": "Lần 1",
    "tx2": "Lần 2",
    "tx3": "Lần 3",
    "tx4": "Lần 4",
    "midterm": "Giữa HK",
    "final": "Cuối HK",
}


def odd_file(imp: ImportApi) -> bytes:
    sheet = imp.score_sheet()
    assert sheet.tx_count == 4
    rows = [[r[1], r[2], *r[3:7], r[7], r[8]] for r in sheet.rows]
    return build_xlsx([ODD_HEADERS, *rows])


def upload_odd(imp: ImportApi, email: str = TOAN_TEACHER, **form: Any) -> Any:
    return imp.upload(
        email,
        "11A2",
        "assessments",
        odd_file(imp),
        subject_id=imp.subject_id_of("Toán"),
        semester=1,
        **form,
    )


def test_missing_required_columns_gives_no_job_and_lists_what_is_missing(imp: ImportApi) -> None:
    body = upload_odd(imp).json()

    assert body["job_id"] is None and body["can_confirm"] is False
    assert body["rows"] == []
    assert "Mã học sinh" in body["missing_required"]
    assert body["detected_columns"] == ODD_HEADERS
    assert count(imp, ImportJob) == 0


def test_explicit_mapping_fixes_the_file_and_can_be_saved_as_a_template(imp: ImportApi) -> None:
    body = upload_odd(imp, mapping=ODD_MAPPING, save_mapping_as="Sổ trường A").json()

    assert body["missing_required"] == [] and body["summary"]["error_rows"] == 0
    assert body["summary"]["unchanged_rows"] == 40
    assert body["job_id"]
    templates = imp.client.get(
        "/api/v1/imports/mappings?kind=assessments", headers=imp.auth_headers(TOAN_TEACHER)
    ).json()
    assert [t["name"] for t in templates] == ["Sổ trường A"]
    assert templates[0]["mapping"] == ODD_MAPPING


def test_saved_template_is_used_by_name_and_belongs_to_its_owner(imp: ImportApi) -> None:
    upload_odd(imp, mapping=ODD_MAPPING, save_mapping_as="Sổ trường A")

    reuse = upload_odd(imp, mapping_name="Sổ trường A").json()
    missing = upload_odd(imp, mapping_name="Không có mẫu này").json()

    assert reuse["missing_required"] == [] and reuse["summary"]["unchanged_rows"] == 40
    assert missing["missing_required"] and any("Không có mẫu" in n for n in missing["notes"])
    others = imp.client.get(
        "/api/v1/imports/mappings", headers=imp.auth_headers("gv.toan.12@example.com")
    ).json()
    assert others == []  # mẫu của giáo viên khác không hiện
    other_use = upload_odd(imp, email="gv.toan.12@example.com", mapping_name="Sổ trường A")
    assert other_use.status_code == 403  # và người đó cũng chẳng có quyền ghi lớp 11A2


def test_saving_a_template_with_the_same_name_replaces_it(imp: ImportApi) -> None:
    upload_odd(imp, mapping=ODD_MAPPING, save_mapping_as="Mẫu")
    changed = ODD_MAPPING | {"midterm": "Cuối HK", "final": "Giữa HK"}
    upload_odd(imp, mapping=changed, save_mapping_as="Mẫu")

    templates = imp.client.get(
        "/api/v1/imports/mappings", headers=imp.auth_headers(TOAN_TEACHER)
    ).json()

    assert len(templates) == 1 and templates[0]["mapping"]["midterm"] == "Cuối HK"


def test_a_malformed_mapping_json_is_rejected(imp: ImportApi) -> None:
    sheet = imp.score_sheet()
    for bad in ("khong-phai-json", "[1, 2]", '{"tx1": 5}'):
        response = imp.upload(
            TOAN_TEACHER,
            "11A2",
            "assessments",
            sheet.to_xlsx(),
            subject_id=imp.subject_id_of("Toán"),
            semester=1,
            mapping=bad,
        )
        assert response.status_code == 422, bad


# --- Môn nhận xét -------------------------------------------------------------------------------


def test_comment_subject_file_with_pass_and_fail(imp: ImportApi) -> None:
    subject = "Giáo dục thể chất"
    stored = {
        code: result
        for (code, kind, _), result in _comment_snapshot(imp, subject).items()
        if kind == "ck"
    }
    codes = sorted(stored)
    flip = {"pass": "Chưa đạt", "fail": "Đạt"}
    rows = [["Mã HS", "Nhận xét"]] + [
        [code, flip[stored[code]] if code == codes[0] else stored[code]] for code in codes
    ]

    body = imp.upload(
        GDTC_TEACHER,
        "11A2",
        "assessments",
        build_csv(rows),
        "gdtc.csv",
        subject_id=imp.subject_id_of(subject),
        semester=1,
    ).json()

    assert body["summary"]["error_rows"] == 0
    assert body["summary"]["changed_rows"] == 1
    assert [f["name"] for f in body["fields"]] == ["student_code", "full_name", "comment_result"]
    result = imp.confirm(GDTC_TEACHER, body["job_id"]).json()
    assert (result["created"], result["updated"]) == (0, 1)
    now = _comment_snapshot(imp, subject)[(codes[0], "ck", 1)]
    assert now == flip[stored[codes[0]]].replace("Chưa đạt", "fail").replace("Đạt", "pass")


def _comment_snapshot(imp: ImportApi, subject: str) -> dict[tuple[str, str, int], str]:
    imp.session.expire_all()
    found = imp.session.execute(
        select(Student.student_code, Assessment.kind, Assessment.seq, Assessment.comment_result)
        .join(ClassStudent, ClassStudent.student_id == Student.id)
        .join(Assessment, Assessment.class_student_id == ClassStudent.id)
        .where(
            ClassStudent.class_id == imp.class_id_of("11A2"),
            Assessment.subject_id == imp.subject_id_of(subject),
            Assessment.semester == 1,
        )
    ).all()
    return {(code, kind.value, seq): result.value for code, kind, seq, result in found}


# --- Điểm danh ----------------------------------------------------------------------------------


def test_attendance_csv_changes_only_the_edited_day(imp: ImportApi) -> None:
    rows = imp.attendance_rows()
    day = rows[0][1]
    one_day = [r for r in rows if r[1] == day]
    assert len(one_day) == 40
    changed_code = one_day[4][0]
    new_status = "absent_unexcused" if one_day[4][2] != "absent_unexcused" else "present"
    sheet = [["Mã HS", "Ngày", "Trạng thái"]] + [
        [code, day.strftime("%d/%m/%Y"), new_status if code == changed_code else status]
        for code, _, status in one_day
    ]
    before = imp.attendance_snapshot()

    body = imp.upload(
        HOMEROOM_11A2, "11A2", "attendance", build_csv(sheet, bom=True), "dd.csv"
    ).json()

    assert body["summary"]["error_rows"] == 0
    assert (body["summary"]["changed_rows"], body["summary"]["unchanged_rows"]) == (1, 39)
    [changed] = [r for r in body["rows"] if r["action"] == "changed"]
    assert changed["existing"] == {"status": one_day[4][2]}
    result = imp.confirm(HOMEROOM_11A2, body["job_id"]).json()
    assert (result["created"], result["updated"]) == (0, 1)
    after = imp.attendance_snapshot()
    assert {k for k in after if after[k] != before[k]} == {(changed_code, day)}
    assert len(after) == len(before)


def test_attendance_for_days_not_yet_in_the_database_is_new_and_idempotent(
    imp: ImportApi,
) -> None:
    rows = imp.attendance_rows()
    day = rows[0][1]
    imp.session.execute(delete(Attendance).where(Attendance.date == day))
    sheet = [["Mã HS", "Ngày", "Trạng thái"]] + [
        [code, day.isoformat(), status] for code, d, status in rows if d == day
    ]
    before = imp.attendance_snapshot()
    assert (rows[0][0], day) not in before

    body = imp.upload(HOMEROOM_11A2, "11A2", "attendance", build_csv(sheet), "dd.csv").json()
    assert body["summary"]["new_rows"] == 40
    result = imp.confirm(HOMEROOM_11A2, body["job_id"]).json()
    assert result["created"] == 40

    again = imp.upload(HOMEROOM_11A2, "11A2", "attendance", build_csv(sheet), "dd.csv").json()
    assert again["summary"]["unchanged_rows"] == 40 and again["summary"]["new_rows"] == 0
    assert len(imp.attendance_snapshot()) == len(before) + 40


def test_attendance_errors_outside_the_school_year_and_duplicates(imp: ImportApi) -> None:
    code = imp.attendance_rows()[0][0]
    sheet = [
        ["Mã HS", "Ngày", "Trạng thái"],
        [code, "01/01/2020", "present"],
        [code, "04/03/2027", "present"],
        [code, "04/03/2027", "late"],
        [code, "ngày mai", "ốm"],
    ]

    body = imp.upload(HOMEROOM_11A2, "11A2", "attendance", build_csv(sheet), "dd.csv").json()

    errors = {
        r["line"]: [m["column"] for m in r["messages"]]
        for r in body["rows"]
        if r["status"] == "error"
    }
    assert errors == {2: ["Ngày"], 4: ["Ngày"], 5: ["Ngày", "Trạng thái"]}
    assert body["can_confirm"] is False


def test_preview_lists_every_error_but_cuts_ordinary_rows_at_500(imp: ImportApi) -> None:
    rows = imp.attendance_rows()[:600]
    sheet = [["Mã HS", "Ngày", "Trạng thái"]] + [
        [code, day.isoformat(), status] for code, day, status in rows
    ]
    sheet[580][2] = "ốm"
    sheet[599][2] = "nghỉ nửa buổi"

    body = imp.upload(HOMEROOM_11A2, "11A2", "attendance", build_csv(sheet), "dd.csv").json()

    assert body["summary"]["total_rows"] == 600 and body["summary"]["error_rows"] == 2
    assert body["truncated"] is True and len(body["rows"]) == 500
    assert {r["line"] for r in body["rows"] if r["status"] == "error"} == {581, 600}
    assert [r["line"] for r in body["rows"]] == sorted(r["line"] for r in body["rows"])


# --- Rèn luyện ----------------------------------------------------------------------------------


def test_conduct_file_updates_the_level_and_keeps_comments_when_blank(imp: ImportApi) -> None:
    stored = imp.conduct_rows()
    assert len(stored) == 40
    before = imp.conduct_snapshot()
    code = stored[2][0]
    new_level = "fail" if stored[2][1] != "fail" else "good"
    sheet = [["Mã HS", "Xếp loại", "Nhận xét"]] + [
        [c, new_level if c == code else lvl, ""] for c, lvl, _ in stored
    ]

    body = imp.upload(
        HOMEROOM_11A2, "11A2", "conduct", build_csv(sheet), "rl.csv", period="hk1"
    ).json()

    assert body["summary"]["error_rows"] == 0 and body["summary"]["changed_rows"] == 1
    assert body["period"] == "hk1"
    imp.confirm(HOMEROOM_11A2, body["job_id"])
    after = imp.conduct_snapshot()
    assert {k for k in after if after[k] != before[k]} == {code}
    assert after[code][0] == new_level and after[code][1] == before[code][1]


def test_conduct_with_an_unknown_level_is_an_error(imp: ImportApi) -> None:
    code = imp.conduct_rows()[0][0]
    sheet = [["Mã HS", "Xếp loại"], [code, "Xuất sắc"]]

    body = imp.upload(
        HOMEROOM_11A2, "11A2", "conduct", build_csv(sheet), "rl.csv", period="hk1"
    ).json()

    assert body["summary"]["error_rows"] == 1 and body["can_confirm"] is False


# --- Hết hạn, không tồn tại ---------------------------------------------------------------------


def test_expired_preview_cannot_be_confirmed(imp: ImportApi) -> None:
    sheet = imp.score_sheet()
    sheet.rows[0][sheet.column("TX1")] = other_score(sheet.rows[0][sheet.column("TX1")])
    before = imp.score_snapshot()
    job_id = imp.upload_scores(TOAN_TEACHER, sheet).json()["job_id"]
    imp.session.execute(
        update(ImportJob).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )

    response = imp.confirm(TOAN_TEACHER, job_id)

    assert response.status_code == 410
    assert imp.score_snapshot() == before


def test_a_new_upload_purges_expired_previews(imp: ImportApi) -> None:
    sheet = imp.score_sheet()
    old_id = imp.upload_scores(TOAN_TEACHER, sheet).json()["job_id"]
    imp.session.execute(update(ImportJob).values(expires_at=datetime.now(UTC) - timedelta(hours=1)))

    imp.upload_scores(TOAN_TEACHER, sheet)

    imp.session.expire_all()
    assert imp.session.get(ImportJob, old_id) is None
    assert count(imp, ImportJob) == 1


def test_the_preview_expires_24_hours_after_it_was_made(imp: ImportApi) -> None:
    body = imp.upload_scores(TOAN_TEACHER, imp.score_sheet()).json()

    expires = datetime.fromisoformat(body["expires_at"])
    assert timedelta(hours=23, minutes=59) < expires - datetime.now(UTC) <= timedelta(hours=24)


def test_confirming_a_job_that_does_not_exist(imp: ImportApi) -> None:
    missing = imp.confirm(TOAN_TEACHER, "00000000-0000-4000-8000-000000000000")
    malformed = imp.confirm(TOAN_TEACHER, "khong-phai-uuid")

    assert missing.status_code == 404
    assert malformed.status_code == 422


# --- Tệp xấu và tham số sai ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("filename", "data", "status"),
    [
        pytest.param("diem.xls", b"x", 415, id="xls"),
        pytest.param("diem.xlsm", b"x", 415, id="xlsm"),
        pytest.param("diem.pdf", b"%PDF", 415, id="pdf"),
        pytest.param("diem.xlsx", b"khong phai excel", 422, id="xlsx-hong"),
        pytest.param("diem.csv", b"", 422, id="csv-rong"),
        pytest.param("diem.csv", b"x" * (5 * 1024 * 1024 + 10), 413, id="qua-5mb"),
    ],
)
def test_bad_files_are_rejected_with_a_clear_status(
    imp: ImportApi, filename: str, data: bytes, status: int
) -> None:
    response = imp.upload(
        TOAN_TEACHER,
        "11A2",
        "assessments",
        data,
        filename,
        subject_id=imp.subject_id_of("Toán"),
        semester=1,
    )

    assert response.status_code == status
    assert isinstance(response.json()["detail"], str)
    assert count(imp, ImportJob) == 0


def test_required_parameters_per_kind(imp: ImportApi) -> None:
    data = build_csv([["Mã HS"], ["HS1"]])
    subject_id = imp.subject_id_of("Toán")

    no_subject = imp.upload(TOAN_TEACHER, "11A2", "assessments", data, "a.csv", semester=1)
    no_semester = imp.upload(
        TOAN_TEACHER, "11A2", "assessments", data, "a.csv", subject_id=subject_id
    )
    bad_semester = imp.upload(
        TOAN_TEACHER, "11A2", "assessments", data, "a.csv", subject_id=subject_id, semester=3
    )
    no_period = imp.upload(HOMEROOM_11A2, "11A2", "conduct", data, "a.csv")
    bad_period = imp.upload(HOMEROOM_11A2, "11A2", "conduct", data, "a.csv", period="hk3")
    bad_kind = imp.upload(HOMEROOM_11A2, "11A2", "ban-ghi-khac", data, "a.csv")

    for response in (no_subject, no_semester, bad_semester, no_period, bad_period, bad_kind):
        assert response.status_code == 422

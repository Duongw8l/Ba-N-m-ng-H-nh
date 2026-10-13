"""Nhập danh sách học sinh qua API (D-100): chỉ Admin, xem trước không lộ dữ liệu cũ, ghi đúng."""

from datetime import date
from typing import Any

import pytest
from sqlalchemy import func, select, update

from app.auth.models import AuditLog, User
from app.classes.models import ClassStudent, SchoolClass, Student
from app.core.enums import AuditAction, ImportStatus, UserRole
from app.imports.models import ImportJob
from tests.imports.conftest import ImportApi, build_csv, build_xlsx

pytestmark = pytest.mark.db

ADMIN = "admin@example.com"
FORBIDDEN = {"detail": "Bạn không có quyền truy cập dữ liệu này."}
HEADER = ["STT", "Mã HS", "Họ và tên", "Ngày sinh", "Họ tên phụ huynh", "Số điện thoại"]
ROWS = [
    [1, "HS9001", "Nguyễn Văn Mới", "05/03/2011", "Nguyễn Văn Cha", "0911 111 111"],
    [2, "HS9002", "Trần Thị Mới", "12/07/2011", "Trần Văn Cha", "0922222222"],
    [3, "HS9003", "Lê Văn Mới", "", "", ""],
]


def roster(rows: list[list[Any]] | None = None, header: list[str] | None = None) -> bytes:
    return build_xlsx([header or HEADER, *(rows if rows is not None else ROWS)])


def make_class(imp: ImportApi, name: str = "11A9", grade: int = 11) -> int:
    year_id = imp.session.scalar(select(SchoolClass.school_year_id).limit(1))
    school_class = SchoolClass(school_year_id=year_id, grade_level=grade, name=name)
    imp.session.add(school_class)
    imp.session.flush()
    return school_class.id


def student_of(imp: ImportApi, code: str) -> Student | None:
    imp.session.expire_all()
    return imp.session.scalar(select(Student).where(Student.student_code == code))


def members(imp: ImportApi, class_id: int) -> list[str]:
    return sorted(
        imp.session.scalars(
            select(Student.student_code)
            .join(ClassStudent, ClassStudent.student_id == Student.id)
            .where(ClassStudent.class_id == class_id)
        )
    )


def count(imp: ImportApi, model: Any) -> int:
    return imp.session.scalar(select(func.count()).select_from(model)) or 0


# --- Phân quyền: chỉ Admin ----------------------------------------


@pytest.mark.parametrize(
    "email",
    [
        "bgh1@example.com",
        "gvcn.11a2@example.com",  # chủ nhiệm 11A2
        "gv.toan.11@example.com",  # chủ nhiệm 11A1, dạy Toán 11A2
        "gv.van.11@example.com",
    ],
)
def test_nobody_but_the_admin_may_preview_a_roster_even_for_their_own_class(
    imp: ImportApi, email: str
) -> None:
    before = (count(imp, Student), count(imp, ClassStudent), count(imp, ImportJob))
    class_id = imp.class_id_of("11A2")

    for target in (class_id, imp.class_id_of("11A1")):
        response = imp.upload(email, target, "roster", roster())
        assert (response.status_code, response.json()) == (403, FORBIDDEN)

    assert (count(imp, Student), count(imp, ClassStudent), count(imp, ImportJob)) == before


def test_unauthenticated_gets_401(imp: ImportApi) -> None:
    assert imp.upload(None, imp.class_id_of("11A2"), "roster", roster()).status_code == 401


def test_permission_is_checked_before_the_file_is_read_or_the_class_looked_up(
    imp: ImportApi,
) -> None:
    junk = b"MZ\x90\x00 khong phai bang tinh"

    denied = imp.upload("gv.van.11@example.com", 999999, "roster", junk, "virus.exe")
    admin_unknown_class = imp.upload(ADMIN, 999999, "roster", roster())
    admin_junk = imp.upload(ADMIN, imp.class_id_of("11A2"), "roster", junk, "virus.exe")

    assert denied.status_code == 403
    assert admin_unknown_class.status_code == 404
    assert admin_junk.status_code == 415  # tới được bước đọc tệp rồi mới báo loại tệp sai


def test_roster_does_not_open_the_admin_to_the_other_kinds(imp: ImportApi) -> None:
    csv_scores = build_csv([["Mã HS", "TX1"], ["HS1102001", "7"]])

    response = imp.upload(
        ADMIN,
        "11A2",
        "assessments",
        csv_scores,
        "d.csv",
        subject_id=imp.subject_id_of("Toán"),
        semester=1,
    )

    assert response.status_code == 403


def test_a_roster_job_can_only_be_confirmed_by_the_admin_who_made_it(imp: ImportApi) -> None:
    class_id = make_class(imp)
    preview = imp.upload(ADMIN, class_id, "roster", roster()).json()
    imp.session.add(
        User(
            email="admin2@example.com",
            full_name="Admin hai",
            password_hash="x",
            role=UserRole.ADMIN,
        )
    )
    imp.session.flush()

    for email in ("bgh1@example.com", "gvcn.11a2@example.com", "admin2@example.com"):
        response = imp.confirm(email, preview["job_id"])
        assert response.status_code == 403, email
    assert imp.confirm(None, preview["job_id"]).status_code == 401
    assert members(imp, class_id) == []


# --- Xem trước ----------------------------------------


def test_preview_maps_the_columns_and_writes_nothing(imp: ImportApi) -> None:
    class_id = make_class(imp)
    before = (count(imp, Student), count(imp, ClassStudent))

    response = imp.upload(ADMIN, class_id, "roster", roster())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "roster" and body["can_confirm"] is True
    assert [f["name"] for f in body["fields"]] == [
        "student_code",
        "full_name",
        "date_of_birth",
        "guardian_name",
        "guardian_phone",
    ]
    assert body["missing_required"] == []
    assert body["summary"]["new_rows"] == 3 and body["summary"]["error_rows"] == 0
    assert [r["student_code"] for r in body["rows"]] == ["HS9001", "HS9002", "HS9003"]
    assert body["rows"][0]["full_name"] == "Nguyễn Văn Mới"  # tên trong tệp
    assert body["rows"][0]["values"]["guardian_phone"] == "0911111111"
    assert (count(imp, Student), count(imp, ClassStudent)) == before


def test_preview_of_a_student_already_in_the_class_never_shows_old_values(
    imp: ImportApi,
) -> None:
    class_id = imp.class_id_of("11A2")  # HS1102001 (em An, có sẵn họ tên và phụ huynh)
    rows = [[1, "HS1102001", "Tên mới trong tệp", "", "", ""]]

    body = imp.upload(ADMIN, class_id, "roster", roster(rows)).json()

    row = body["rows"][0]
    assert row["action"] == "changed" and row["existing"] == {}
    assert row["full_name"] == "Tên mới trong tệp"
    assert "Trần Minh An" not in str(body)  # tên đang lưu trong hệ thống không lộ ra


def test_preview_blocks_a_student_of_another_class_and_a_repeated_code(imp: ImportApi) -> None:
    class_id = make_class(imp)
    rows = [
        [1, "HS1102001", "Em ở lớp khác", "", "", ""],
        [2, "HS9001", "Một", "", "", ""],
        [3, "hs9001", "Hai", "", "", ""],
        [4, "HS9004", "Ba", "abc", "", ""],
    ]

    body = imp.upload(ADMIN, class_id, "roster", roster(rows)).json()

    assert body["can_confirm"] is False and body["job_id"] is not None
    assert body["summary"]["error_rows"] == 3
    other_class, ok, repeated, bad_date = body["rows"]
    assert "đã thuộc lớp 11A2" in other_class["messages"][0]["message"]
    assert ok["status"] == "ok"
    assert "trùng với dòng 3" in repeated["messages"][0]["message"]
    assert bad_date["messages"][0]["column"] == "Ngày sinh"
    assert imp.confirm(ADMIN, body["job_id"]).status_code == 422
    assert members(imp, class_id) == []


def test_preview_reports_a_missing_required_column(imp: ImportApi) -> None:
    class_id = make_class(imp)

    body = imp.upload(
        ADMIN, class_id, "roster", build_xlsx([["Mã HS", "Lớp"], ["HS1", "x"]])
    ).json()

    assert body["job_id"] is None and body["can_confirm"] is False
    assert body["missing_required"] == ["Họ và tên"]


def test_a_csv_roster_with_a_custom_column_choice_works(imp: ImportApi) -> None:
    class_id = make_class(imp)
    data = build_csv([["Ma so", "Ten", "Dien thoai"], ["HS9100", "Phạm Văn Csv", "912345678"]])

    body = imp.upload(
        ADMIN,
        class_id,
        "roster",
        data,
        "ds.csv",
        mapping={"student_code": "Ma so", "full_name": "Ten", "guardian_phone": "Dien thoai"},
    ).json()

    assert body["can_confirm"] is True
    assert body["rows"][0]["status"] == "warning"  # Excel mất số 0 đầu, đã bù
    assert body["rows"][0]["values"]["guardian_phone"] == "0912345678"


# --- Xác nhận ----------------------------------------


def test_confirm_adds_new_students_to_the_class_and_the_homeroom_teacher_sees_them(
    imp: ImportApi,
) -> None:
    class_id = make_class(imp)
    imp.session.add(
        User(
            email="gvcn.lop.moi@example.com",
            full_name="GVCN lớp mới",
            password_hash="x",
            role=UserRole.TEACHER,
        )
    )
    imp.session.flush()
    teacher_id = imp.session.scalar(select(User.id).where(User.email == "gvcn.lop.moi@example.com"))
    imp.session.get(SchoolClass, class_id).homeroom_teacher_id = teacher_id  # type: ignore[union-attr]
    imp.session.flush()
    job_id = imp.upload(ADMIN, class_id, "roster", roster()).json()["job_id"]

    response = imp.confirm(ADMIN, job_id)

    assert response.status_code == 200, response.text
    assert response.json()["created"] == 3 and response.json()["updated"] == 0
    assert members(imp, class_id) == ["HS9001", "HS9002", "HS9003"]
    first = student_of(imp, "HS9001")
    assert first is not None
    assert (first.full_name, first.date_of_birth) == ("Nguyễn Văn Mới", date(2011, 3, 5))
    assert (first.guardian_name, first.guardian_phone) == ("Nguyễn Văn Cha", "0911111111")
    third = student_of(imp, "HS9003")
    assert third is not None and third.date_of_birth is None and third.guardian_phone is None
    # GVCN của lớp thấy danh sách kèm phụ huynh; Admin vẫn không xem được (D-039).
    listed = imp.client.get(
        f"/api/v1/classes/{class_id}/students", headers=imp.auth_headers("gvcn.lop.moi@example.com")
    )
    assert listed.status_code == 200
    assert [s["student_code"] for s in listed.json()] == ["HS9001", "HS9002", "HS9003"]
    assert listed.json()[0]["guardian_phone"] == "0911111111"
    denied = imp.client.get(f"/api/v1/classes/{class_id}/students", headers=imp.auth_headers(ADMIN))
    assert denied.status_code == 403


def test_confirm_clears_the_personal_data_stored_in_the_job_and_logs_without_it(
    imp: ImportApi,
) -> None:
    class_id = make_class(imp)
    job_id = imp.upload(ADMIN, class_id, "roster", roster()).json()["job_id"]
    job = imp.session.get(ImportJob, job_id)
    assert job is not None and "Nguyễn Văn Mới" in str(job.rows)  # có trong job đến khi xác nhận

    imp.confirm(ADMIN, job_id)

    imp.session.expire_all()
    job = imp.session.get(ImportJob, job_id)
    assert job is not None and job.status is ImportStatus.CONFIRMED
    assert job.rows == []
    assert "Nguyễn" not in str(job.summary) and "0911" not in str(job.summary)
    logged = imp.session.scalars(
        select(AuditLog).where(AuditLog.action == AuditAction.IMPORT_CONFIRM)
    ).all()
    assert logged[-1].class_id == class_id
    assert logged[-1].details["kind"] == "roster" and logged[-1].details["created"] == 3
    assert "Nguyễn" not in str(logged[-1].details) and "0911" not in str(logged[-1].details)


def test_confirm_twice_does_not_write_twice(imp: ImportApi) -> None:
    class_id = make_class(imp)
    job_id = imp.upload(ADMIN, class_id, "roster", roster()).json()["job_id"]

    first = imp.confirm(ADMIN, job_id)
    students_after_first = count(imp, Student)
    second = imp.confirm(ADMIN, job_id)

    assert first.json()["already_confirmed"] is False
    assert second.status_code == 200 and second.json()["already_confirmed"] is True
    assert count(imp, Student) == students_after_first


def test_importing_again_updates_the_students_and_keeps_info_the_file_leaves_empty(
    imp: ImportApi,
) -> None:
    class_id = make_class(imp)
    imp.confirm(ADMIN, imp.upload(ADMIN, class_id, "roster", roster()).json()["job_id"])
    again = [
        [1, "HS9001", "Nguyễn Văn Đổi Tên", "", "", ""],  # ô trống: giữ ngày sinh, phụ huynh cũ
        [2, "HS9002", "Trần Thị Mới", "", "Người mới", "0933 333 333"],
        [3, "HS9004", "Thêm Một Em", "", "", ""],
    ]

    preview = imp.upload(ADMIN, class_id, "roster", roster(again)).json()
    result = imp.confirm(ADMIN, preview["job_id"]).json()

    assert [r["action"] for r in preview["rows"]] == ["changed", "changed", "new"]
    assert (result["created"], result["updated"]) == (1, 2)
    assert members(imp, class_id) == ["HS9001", "HS9002", "HS9003", "HS9004"]
    first, second = student_of(imp, "HS9001"), student_of(imp, "HS9002")
    assert first is not None and second is not None
    assert first.full_name == "Nguyễn Văn Đổi Tên"
    assert first.date_of_birth == date(2011, 3, 5) and first.guardian_name == "Nguyễn Văn Cha"
    assert (second.guardian_name, second.guardian_phone) == ("Người mới", "0933333333")
    assert second.date_of_birth == date(2011, 7, 12)  # giữ nguyên


def test_a_record_stored_with_a_lower_case_code_is_updated_not_duplicated(
    imp: ImportApi,
) -> None:
    class_id = make_class(imp)
    imp.session.add(
        Student(student_code="hs9500", full_name="Hồ sơ cũ", guardian_phone="0900000001")
    )
    imp.session.flush()
    before = count(imp, Student)

    preview = imp.upload(
        ADMIN, class_id, "roster", roster([[1, "HS9500", "Tên cập nhật", "", "", ""]])
    )
    imp.confirm(ADMIN, preview.json()["job_id"])

    assert count(imp, Student) == before  # không tạo bản sao HS9500
    student = student_of(imp, "hs9500")
    assert student is not None and student.full_name == "Tên cập nhật"
    assert student.guardian_phone == "0900000001"
    assert members(imp, class_id) == ["hs9500"]


def test_an_admin_demoted_after_the_preview_can_no_longer_confirm_it(imp: ImportApi) -> None:
    class_id = make_class(imp)
    imp.session.add(
        User(
            email="admin.tam@example.com",
            full_name="Admin tạm",
            password_hash="x",
            role=UserRole.ADMIN,
        )
    )
    imp.session.flush()
    job_id = imp.upload("admin.tam@example.com", class_id, "roster", roster()).json()["job_id"]
    imp.session.execute(
        update(User).where(User.email == "admin.tam@example.com").values(role=UserRole.TEACHER)
    )

    response = imp.confirm("admin.tam@example.com", job_id)

    assert response.status_code == 403
    assert members(imp, class_id) == []


def test_a_student_record_without_a_class_is_attached_not_duplicated(imp: ImportApi) -> None:
    class_id = make_class(imp)
    imp.session.add(Student(student_code="HS9600", full_name="Em chưa có lớp"))
    imp.session.flush()

    preview = imp.upload(
        ADMIN, class_id, "roster", roster([[1, "HS9600", "Em chưa có lớp", "", "", ""]])
    )

    assert preview.json()["rows"][0]["action"] == "new"  # sẽ thêm vào lớp
    result = imp.confirm(ADMIN, preview.json()["job_id"]).json()
    assert (result["created"], result["updated"]) == (1, 0)
    assert members(imp, class_id) == ["HS9600"]


def test_a_student_who_joined_another_class_since_the_preview_is_refused_at_confirm(
    imp: ImportApi,
) -> None:
    # Hai bản xem trước cho hai lớp có cùng một mã: cả hai hợp lệ lúc xem trước vì chưa lớp nào có
    # em đó. Xác nhận bản đầu xong thì bản sau phải bị từ chối, không để một học sinh ở hai lớp.
    first = make_class(imp, "11A8")
    second = make_class(imp, "11A7")
    rows = roster([[1, "HS9700", "Em đăng ký hai lớp", "", "", ""]])
    job_a = imp.upload(ADMIN, first, "roster", rows).json()["job_id"]
    job_b = imp.upload(ADMIN, second, "roster", rows).json()["job_id"]

    assert imp.confirm(ADMIN, job_a).status_code == 200
    refused = imp.confirm(ADMIN, job_b)

    assert refused.status_code == 409
    assert members(imp, first) == ["HS9700"] and members(imp, second) == []
    assert student_of(imp, "HS9700") is not None

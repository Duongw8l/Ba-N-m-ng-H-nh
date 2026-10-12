"""Phân quyền GHI của nhập tệp (D-058): ma trận 4 vai trò × 3 loại, kiểm trước khi đọc tệp.

Tài khoản (README): gvcn.11a2 chỉ chủ nhiệm 11A2; gv.toan.11 chủ nhiệm 11A1 và dạy Toán ở 11A1,
11A2, 11A3 (cộng dồn); gv.van.11 dạy Ngữ văn ở cả 3 lớp 11; gv.toan.12 chủ nhiệm 12A1 và dạy
Toán khối 12; bgh1 là BGH; admin là Admin.
"""

import pytest
from sqlalchemy import delete, func, select, update

from app.auth.models import AuditLog, User
from app.classes.models import SchoolClass, TeachingAssignment
from app.imports.models import ImportJob
from tests.imports.conftest import ImportApi, build_csv

pytestmark = pytest.mark.db

FORBIDDEN = {"detail": "Bạn không có quyền truy cập dữ liệu này."}

# (email, lớp, môn, được ghi?)
SCORE_CASES = [
    ("gv.toan.11@example.com", "11A2", "Toán", True),  # dạy đúng lớp-môn
    ("gv.toan.11@example.com", "11A1", "Toán", True),  # vừa chủ nhiệm vừa dạy
    ("gv.van.11@example.com", "11A2", "Ngữ văn", True),
    ("gv.toan.12@example.com", "12A1", "Toán", True),
    ("gv.van.11@example.com", "11A2", "Toán", False),  # môn khác
    ("gv.toan.11@example.com", "11A2", "Ngữ văn", False),  # dạy Toán, không dạy Văn
    ("gv.toan.11@example.com", "11A1", "Ngữ văn", False),  # chủ nhiệm lớp đó nhưng không dạy Văn
    ("gvcn.11a2@example.com", "11A2", "Toán", False),  # GVCN thuần không dạy môn nào
    ("gv.toan.11@example.com", "12A1", "Toán", False),  # khối khác
    ("gv.toan.12@example.com", "11A2", "Toán", False),
    ("bgh1@example.com", "11A2", "Toán", False),  # BGH xem được nhưng không ghi
    ("admin@example.com", "11A2", "Toán", False),
]
HOMEROOM_CASES = [
    ("gvcn.11a2@example.com", "11A2", True),
    ("gv.toan.11@example.com", "11A1", True),  # cộng dồn: chủ nhiệm 11A1
    ("gv.toan.12@example.com", "12A1", True),
    ("gv.toan.11@example.com", "11A2", False),  # dạy Toán ở đó nhưng không chủ nhiệm
    ("gv.van.11@example.com", "11A2", False),
    ("gvcn.11a2@example.com", "11A3", False),  # GVCN lớp khác cùng khối
    ("gvcn.11a2@example.com", "10A1", False),
    ("bgh1@example.com", "11A2", False),
    ("admin@example.com", "11A2", False),
]


def tiny_csv(*header: str) -> bytes:
    return build_csv([list(header)])


@pytest.mark.parametrize(("email", "class_name", "subject", "allowed"), SCORE_CASES)
def test_who_may_import_scores(
    imp: ImportApi, email: str, class_name: str, subject: str, allowed: bool
) -> None:
    response = imp.upload(
        email,
        class_name,
        "assessments",
        tiny_csv("Mã HS"),
        "diem.csv",
        subject_id=imp.subject_id_of(subject),
        semester=1,
    )

    if allowed:
        assert response.status_code == 200, response.text
        assert response.json()["missing_required"]  # tới được bước đọc tệp, chỉ thiếu cột
    else:
        assert response.status_code == 403
        assert response.json() == FORBIDDEN


@pytest.mark.parametrize("kind", ["attendance", "conduct"])
@pytest.mark.parametrize(("email", "class_name", "allowed"), HOMEROOM_CASES)
def test_who_may_import_attendance_and_conduct(
    imp: ImportApi, kind: str, email: str, class_name: str, allowed: bool
) -> None:
    form = {"period": "hk1"} if kind == "conduct" else {}
    response = imp.upload(email, class_name, kind, tiny_csv("Mã HS"), "tep.csv", **form)

    if allowed:
        assert response.status_code == 200, response.text
    else:
        assert response.status_code == 403
        assert response.json() == FORBIDDEN


def test_a_subject_teacher_cannot_import_attendance_even_in_their_own_class(
    imp: ImportApi,
) -> None:
    # Cộng dồn tính riêng từng lớp: gv.toan.11 chủ nhiệm 11A1 (được), chỉ dạy Toán ở 11A3 (không).
    allowed = imp.upload("gv.toan.11@example.com", "11A1", "attendance", tiny_csv("Mã HS"), "a.csv")
    denied = imp.upload("gv.toan.11@example.com", "11A3", "attendance", tiny_csv("Mã HS"), "a.csv")

    assert (allowed.status_code, denied.status_code) == (200, 403)


@pytest.mark.parametrize("kind", ["assessments", "attendance", "conduct"])
def test_permission_is_checked_before_the_file_is_read(imp: ImportApi, kind: str) -> None:
    """Gửi tệp rác kiểu .exe mà không có quyền vẫn nhận 403, không phải 415: tệp chưa được đọc."""
    response = imp.upload(
        "gv.van.11@example.com",
        "11A2",
        kind,
        b"MZ\x90\x00 khong phai bang tinh",
        "virus.exe",
        subject_id=imp.subject_id_of("Toán"),
        semester=1,
        period="hk1",
    )

    assert response.status_code == 403
    assert response.json() == FORBIDDEN


def test_a_class_that_does_not_exist_is_403_for_everyone_who_cannot_write(imp: ImportApi) -> None:
    for email in ("gvcn.11a2@example.com", "bgh1@example.com", "admin@example.com"):
        response = imp.upload(email, 999999, "attendance", tiny_csv("Mã HS"), "a.csv")
        assert response.status_code == 403, email


def test_unknown_subject_id_is_403_not_a_hint_that_it_does_not_exist(imp: ImportApi) -> None:
    response = imp.upload(
        "gv.toan.11@example.com",
        "11A2",
        "assessments",
        tiny_csv("Mã HS"),
        "a.csv",
        subject_id=999999,
        semester=1,
    )

    assert response.status_code == 403


def test_nothing_is_stored_when_permission_is_denied(imp: ImportApi) -> None:
    imp.upload(
        "gv.van.11@example.com",
        "11A2",
        "assessments",
        imp.score_sheet().to_xlsx(),
        subject_id=imp.subject_id_of("Toán"),
        semester=1,
    )

    assert imp.session.scalar(select(func.count()).select_from(ImportJob)) == 0


# --- Chưa đăng nhập -----------------------------------------------------------------------------


def test_every_import_endpoint_needs_a_login(imp: ImportApi) -> None:
    upload = imp.upload(None, "11A2", "attendance", tiny_csv("Mã HS"), "a.csv")
    confirm = imp.confirm(None, "00000000-0000-4000-8000-000000000000")
    templates = imp.client.get("/api/v1/imports/mappings")

    assert (upload.status_code, confirm.status_code, templates.status_code) == (401, 401, 401)


# --- Xác nhận: chỉ người tạo, kiểm lại quyền -----------------------------------------------------


def make_job(imp: ImportApi) -> str:
    sheet = imp.score_sheet()
    sheet.rows[0][sheet.column("TX1")] = 9.0 if sheet.rows[0][sheet.column("TX1")] != 9.0 else 8.0
    return imp.upload_scores("gv.toan.11@example.com", sheet).json()["job_id"]


@pytest.mark.parametrize(
    "email",
    [
        "gv.van.11@example.com",  # giáo viên khác
        "gv.toan.12@example.com",  # cùng môn, khối khác
        "gvcn.11a2@example.com",  # chủ nhiệm lớp đó
        "bgh1@example.com",
        "admin@example.com",
    ],
)
def test_only_the_person_who_made_the_preview_can_confirm_it(imp: ImportApi, email: str) -> None:
    job_id = make_job(imp)
    before = imp.score_snapshot()

    response = imp.confirm(email, job_id)

    assert response.status_code == 403 and response.json() == FORBIDDEN
    assert imp.score_snapshot() == before


def test_confirm_checks_the_write_permission_again(imp: ImportApi) -> None:
    """Giáo viên bị rút phân công giữa lúc xem trước và lúc xác nhận thì không ghi được nữa."""
    job_id = make_job(imp)
    before = imp.score_snapshot()
    teacher_id = imp.session.scalar(
        select(User.id).where(func.lower(User.email) == "gv.toan.11@example.com")
    )
    class_id = imp.session.scalar(select(SchoolClass.id).where(SchoolClass.name == "11A2"))
    imp.session.execute(
        delete(TeachingAssignment).where(
            TeachingAssignment.teacher_id == teacher_id,
            TeachingAssignment.class_id == class_id,
            TeachingAssignment.subject_id == imp.subject_id_of("Toán"),
        )
    )

    response = imp.confirm("gv.toan.11@example.com", job_id)

    assert response.status_code == 403
    assert imp.score_snapshot() == before


def test_a_new_teacher_of_the_subject_cannot_confirm_the_previous_teachers_preview(
    imp: ImportApi,
) -> None:
    """Bản xem trước thuộc về người tạo nó, kể cả khi người khác nay có quyền ghi lớp-môn đó."""
    job_id = make_job(imp)
    before = imp.score_snapshot()
    new_teacher = imp.session.scalar(
        select(User.id).where(func.lower(User.email) == "gv.van.11@example.com")
    )
    imp.session.execute(
        update(TeachingAssignment)
        .where(
            TeachingAssignment.class_id == imp.class_id_of("11A2"),
            TeachingAssignment.subject_id == imp.subject_id_of("Toán"),
        )
        .values(teacher_id=new_teacher)
    )

    by_new = imp.confirm("gv.van.11@example.com", job_id)
    by_old = imp.confirm("gv.toan.11@example.com", job_id)

    assert (by_new.status_code, by_old.status_code) == (403, 403)
    assert imp.score_snapshot() == before


def test_a_denied_confirm_leaves_no_audit_row(imp: ImportApi) -> None:
    job_id = make_job(imp)

    imp.confirm("gv.van.11@example.com", job_id)

    assert imp.session.scalar(select(func.count()).select_from(AuditLog)) == 0

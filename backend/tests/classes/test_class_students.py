"""GET /classes/{id}/students: ma trận 4 vai trò × lớp được / không được xem, 401, và nhật ký."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import AuditLog, User
from app.auth.tokens import create_access_token
from app.core.enums import AuditAction

pytestmark = pytest.mark.db

HeadersFor = Callable[[str], dict[str, str]]
FORBIDDEN = {"detail": "Bạn không có quyền truy cập dữ liệu này."}
BASE_KEYS = {"id", "student_code", "full_name"}
GUARDIAN_KEYS = BASE_KEYS | {"guardian_name", "guardian_phone"}

# (email, lớp, thấy phụ huynh?) — các ca được phép.
ALLOWED = [
    ("bgh1@example.com", "10A1", True),
    ("bgh1@example.com", "11A2", True),
    ("bgh1@example.com", "12A3", True),
    ("gvcn.10a2@example.com", "10A2", True),  # GVCN thuần, lớp mình chủ nhiệm
    ("gv.dia.10@example.com", "10A1", False),  # GVBM, lớp có phân công
    ("gv.van.10@example.com", "10A1", False),
    ("gv.van.10@example.com", "10A3", False),
    ("gv.toan.10@example.com", "10A1", True),  # cộng dồn: lớp chủ nhiệm có phụ huynh
    ("gv.toan.10@example.com", "10A2", False),  # cộng dồn: lớp chỉ dạy Toán không có phụ huynh
]
# (email, lớp) — các ca bị từ chối.
DENIED = [
    ("admin@example.com", "10A1"),
    ("admin@example.com", "12A3"),
    ("gvcn.10a2@example.com", "10A1"),  # GVCN lớp khác cùng khối
    ("gvcn.10a2@example.com", "10A3"),
    ("gvcn.10a2@example.com", "11A2"),
    ("gv.dia.10@example.com", "10A2"),  # đúng khối, sai lớp
    ("gv.dia.10@example.com", "10A3"),
    ("gv.dia.10@example.com", "11A1"),  # sai khối
    ("gv.van.10@example.com", "11A1"),
    ("gv.toan.10@example.com", "11A1"),  # chủ nhiệm lớp 10A1 không có quyền gì ở khối 11
    ("gv.toan.10@example.com", "12A1"),
]


def students_url(class_id: int) -> str:
    return f"/api/v1/classes/{class_id}/students"


@pytest.mark.parametrize(("email", "class_name", "sees_guardian"), ALLOWED)
def test_allowed_roles_get_the_class_with_or_without_guardian(
    api_client: TestClient,
    auth_headers: HeadersFor,
    class_id_of: Callable[[str], int],
    email: str,
    class_name: str,
    sees_guardian: bool,
) -> None:
    response = api_client.get(students_url(class_id_of(class_name)), headers=auth_headers(email))

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 40
    expected_keys = GUARDIAN_KEYS if sees_guardian else BASE_KEYS
    assert all(set(row) == expected_keys for row in rows)
    if not sees_guardian:
        assert "guardian" not in response.text  # không có khoá lẫn giá trị phụ huynh
    codes = [row["student_code"] for row in rows]
    assert codes == sorted(codes)
    grade, number = class_name[:2], class_name[-1]
    assert all(code.startswith(f"HS{grade}0{number}") for code in codes)


@pytest.mark.parametrize(("email", "class_name"), DENIED)
def test_everyone_else_gets_403_without_any_data(
    api_client: TestClient,
    auth_headers: HeadersFor,
    class_id_of: Callable[[str], int],
    email: str,
    class_name: str,
) -> None:
    response = api_client.get(students_url(class_id_of(class_name)), headers=auth_headers(email))

    assert response.status_code == 403
    assert response.json() == FORBIDDEN


def test_guardian_data_comes_from_the_students_of_that_class(
    api_client: TestClient, auth_headers: HeadersFor, class_id_of: Callable[[str], int]
) -> None:
    response = api_client.get(
        students_url(class_id_of("11A2")), headers=auth_headers("bgh1@example.com")
    )

    first = response.json()[0]
    assert first["student_code"] == "HS1102001"
    assert first["full_name"] == "Trần Minh An"
    assert first["guardian_phone"].startswith("0000")  # số giả, không hợp lệ


def test_nonexistent_class_is_403_for_teachers_and_admin_but_404_for_principal(
    api_client: TestClient, auth_headers: HeadersFor
) -> None:
    for email in ("gvcn.10a2@example.com", "gv.dia.10@example.com", "admin@example.com"):
        assert api_client.get(students_url(999_999), headers=auth_headers(email)).status_code == 403
    assert (
        api_client.get(students_url(999_999), headers=auth_headers("bgh1@example.com")).status_code
        == 404
    )


# --- Xác thực ----------------------------------------------------------------------------------


def test_missing_or_bad_credentials_get_401_before_any_authorization(
    api_client: TestClient, db_session: Session, class_id_of: Callable[[str], int]
) -> None:
    url = students_url(class_id_of("10A1"))
    admin_id = db_session.scalar(select(User.id).where(User.email == "admin@example.com"))
    assert admin_id is not None
    expired, _ = create_access_token(admin_id, now=datetime.now(UTC) - timedelta(hours=3))
    unknown_user, _ = create_access_token(999_999)  # tài khoản đã bị xoá / không tồn tại
    bad_headers = [
        {},  # không có header
        {"Authorization": "Bearer khong.phai.token"},
        {"Authorization": f"Bearer {expired}"},
        {"Authorization": f"Bearer {unknown_user}"},
        {"Authorization": f"Basic {unknown_user}"},  # sai kiểu xác thực
        {"Authorization": "Bearer"},
    ]

    for headers in bad_headers:
        response = api_client.get(url, headers=headers)
        assert response.status_code == 401, headers
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.json() == {"detail": "Cần đăng nhập."}


def test_role_change_takes_effect_immediately_because_role_is_not_in_the_token(
    api_client: TestClient,
    auth_headers: HeadersFor,
    db_session: Session,
    class_id_of: Callable[[str], int],
) -> None:
    headers = auth_headers("bgh1@example.com")
    url = students_url(class_id_of("12A2"))
    assert api_client.get(url, headers=headers).status_code == 200

    principal = db_session.scalar(select(User).where(User.email == "bgh1@example.com"))
    assert principal is not None
    principal.role = "admin"  # type: ignore[assignment]  # cùng token cũ, vai trò mới
    db_session.flush()

    assert api_client.get(url, headers=headers).status_code == 403


# --- Nhật ký truy cập ----------------------------------------------------------------------------


def audit_rows(session: Session) -> list[AuditLog]:
    return list(session.scalars(select(AuditLog).order_by(AuditLog.id)))


def test_every_successful_open_writes_one_audit_row_and_denials_write_none(
    api_client: TestClient,
    auth_headers: HeadersFor,
    db_session: Session,
    class_id_of: Callable[[str], int],
) -> None:
    assert audit_rows(db_session) == []

    api_client.get(students_url(class_id_of("12A3")), headers=auth_headers("admin@example.com"))
    api_client.get(students_url(class_id_of("10A2")), headers=auth_headers("gv.dia.10@example.com"))
    assert audit_rows(db_session) == []  # 403 không ghi

    api_client.get(students_url(class_id_of("11A2")), headers=auth_headers("bgh1@example.com"))
    api_client.get(students_url(class_id_of("10A1")), headers=auth_headers("gv.dia.10@example.com"))
    api_client.get(students_url(999_999), headers=auth_headers("bgh1@example.com"))  # 404 không ghi

    rows = audit_rows(db_session)
    assert len(rows) == 2
    principal_row, teacher_row = rows
    users = {
        u.email: u.id
        for u in db_session.scalars(select(User))
        if u.email.startswith(("bgh1", "gv.dia.10"))
    }
    assert principal_row.user_id == users["bgh1@example.com"]
    assert principal_row.action is AuditAction.VIEW_CLASS_STUDENTS
    assert principal_row.class_id == class_id_of("11A2")
    assert principal_row.details == {"student_count": 40, "guardian_included": True}
    assert principal_row.created_at is not None
    assert teacher_row.user_id == users["gv.dia.10@example.com"]
    assert teacher_row.class_id == class_id_of("10A1")
    assert teacher_row.details == {"student_count": 40, "guardian_included": False}

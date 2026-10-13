"""Quản lý tài khoản của Admin và đổi mật khẩu (D-096, D-097): phân quyền 4 vai trò + quy tắc."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import AuditLog, User
from app.auth.tokens import create_access_token
from app.core.enums import AuditAction
from app.core.security import verify_password
from data.seed.people import DEV_PASSWORD

pytestmark = pytest.mark.db

API = "/api/v1"
ADMIN = "admin@example.com"
# Mọi vai trò khác Admin: BGH, GVCN, GVBM thuần, và GVBM kiêm GVCN.
NON_ADMINS = [
    "bgh1@example.com",
    "gvcn.11a2@example.com",
    "gv.van.11@example.com",
    "gv.toan.10@example.com",
]
Headers = Callable[[str], dict[str, str]]
NEW_USER = {"email": "Giao.Vien.Moi@Example.com", "full_name": "Phạm Thị Mới", "role": "teacher"}


def user_id(session: Session, email: str) -> int:
    found = session.scalar(select(User.id).where(func.lower(User.email) == email.lower()))
    assert found is not None
    return found


def audit_rows(session: Session, action: AuditAction) -> list[AuditLog]:
    return list(session.scalars(select(AuditLog).where(AuditLog.action == action)))


def create(client: TestClient, headers: dict[str, str], **overrides: Any) -> Response:
    return client.post(f"{API}/admin/users", headers=headers, json={**NEW_USER, **overrides})


def login(client: TestClient, email: str, password: str) -> Response:
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


# --- Phân quyền: 4 vai trò × 4 endpoint quản trị + chưa đăng nhập --------------------------------


def endpoints(target_id: int) -> list[tuple[str, str, dict[str, Any] | None]]:
    return [
        ("GET", f"{API}/admin/users", None),
        ("POST", f"{API}/admin/users", NEW_USER),
        ("PATCH", f"{API}/admin/users/{target_id}", {"full_name": "Tên khác"}),
        ("POST", f"{API}/admin/users/{target_id}/reset-password", None),
    ]


def test_admin_can_use_every_endpoint(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    target = user_id(db_session, "gv.van.11@example.com")

    for method, url, body in endpoints(target):
        response = api_client.request(method, url, headers=headers, json=body)
        assert response.status_code in (200, 201), (method, url, response.text)


@pytest.mark.parametrize("email", NON_ADMINS)
def test_every_other_role_gets_403_on_every_endpoint(
    api_client: TestClient, auth_headers: Headers, db_session: Session, email: str
) -> None:
    headers = auth_headers(email)
    target = user_id(db_session, "gv.van.11@example.com")
    users_before = db_session.scalar(select(func.count()).select_from(User))

    for method, url, body in endpoints(target):
        response = api_client.request(method, url, headers=headers, json=body)
        assert response.status_code == 403, (method, url)
    # Yêu cầu sai hình dạng cũng 403 chứ không 422: quyền được kiểm trước.
    assert api_client.post(f"{API}/admin/users", headers=headers, json={}).status_code == 403
    assert db_session.scalar(select(func.count()).select_from(User)) == users_before


def test_unauthenticated_gets_401_on_every_endpoint(
    api_client: TestClient, db_session: Session
) -> None:
    target = user_id(db_session, "gv.van.11@example.com")

    for method, url, body in endpoints(target):
        assert api_client.request(method, url, json=body).status_code == 401, (method, url)


# --- Danh sách ----------------------------------------------------------------------------------


def test_list_has_roles_homeroom_and_assignments_and_never_a_password_hash(
    api_client: TestClient, auth_headers: Headers
) -> None:
    response = api_client.get(f"{API}/admin/users", headers=auth_headers(ADMIN))

    assert response.status_code == 200
    assert "password" not in response.text
    by_email = {row["email"]: row for row in response.json()}
    homeroom = by_email["gvcn.11a2@example.com"]
    assert homeroom["homeroom_class"] == "11A2"
    assert homeroom["role"] == "teacher"
    assert homeroom["role_label"] == "Giáo viên"
    assert homeroom["is_active"] is True
    assert by_email["gv.van.11@example.com"]["assignment_count"] > 0
    assert by_email["gv.van.11@example.com"]["homeroom_class"] is None  # GVBM thuần
    assert by_email["gv.toan.11@example.com"]["homeroom_class"] == "11A1"  # kiêm chủ nhiệm
    assert by_email["bgh1@example.com"]["role_label"] == "Ban giám hiệu"
    assert set(homeroom) == {
        "id",
        "email",
        "full_name",
        "role",
        "role_label",
        "is_active",
        "homeroom_class",
        "assignment_count",
    }


def test_list_filters_by_role_status_and_text(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    api_client.patch(
        f"{API}/admin/users/{user_id(db_session, 'gv.van.11@example.com')}",
        headers=headers,
        json={"is_active": False},
    )

    admins = api_client.get(f"{API}/admin/users?role=admin", headers=headers).json()
    locked = api_client.get(f"{API}/admin/users?active=false", headers=headers).json()
    found = api_client.get(f"{API}/admin/users?q=BGH1", headers=headers).json()
    nothing = api_client.get(f"{API}/admin/users?q=khong-co-ai", headers=headers).json()

    assert [row["email"] for row in admins] == [ADMIN]
    assert [row["email"] for row in locked] == ["gv.van.11@example.com"]
    assert [row["email"] for row in found] == ["bgh1@example.com"]
    assert nothing == []


# --- Tạo tài khoản và mật khẩu tạm ---------------------------------------------------------------


def test_create_returns_a_one_time_password_that_works_and_is_never_stored_in_clear(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    response = create(api_client, auth_headers(ADMIN))

    assert response.status_code == 201
    body = response.json()
    password = body["temporary_password"]
    assert len(password) == 12
    assert body["user"]["email"] == "giao.vien.moi@example.com"  # chuẩn hoá chữ thường
    assert body["user"]["role"] == "teacher"
    assert body["user"]["is_active"] is True
    assert "password_hash" not in response.text

    stored = db_session.scalar(select(User).where(User.id == body["user"]["id"]))
    assert stored is not None
    assert stored.password_hash != password
    assert verify_password(password, stored.password_hash)
    assert login(api_client, "GIAO.VIEN.MOI@example.com", password).status_code == 200

    # Mật khẩu không nằm trong nhật ký nào.
    logged = audit_rows(db_session, AuditAction.CREATE_USER)
    assert len(logged) == 1
    assert logged[0].details == {"user_id": body["user"]["id"], "role": "teacher"}
    assert password not in str([row.details for row in db_session.scalars(select(AuditLog))])


def test_create_rejects_a_duplicate_email_in_any_case(
    api_client: TestClient, auth_headers: Headers
) -> None:
    headers = auth_headers(ADMIN)

    assert create(api_client, headers, email="ADMIN@example.com").status_code == 409
    first = create(api_client, headers)
    again = create(api_client, headers, email="giao.vien.moi@EXAMPLE.COM")

    assert first.status_code == 201
    assert again.status_code == 409
    assert "Email" in again.json()["detail"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "khong-co-a-cong"},
        {"email": "thieu@mien"},
        {"email": "co khoang@example.com"},
        {"full_name": "   "},
        {"full_name": "x" * 101},
        {"role": "hieu-truong"},
    ],
)
def test_create_validates_the_request(
    api_client: TestClient, auth_headers: Headers, overrides: dict[str, str]
) -> None:
    assert create(api_client, auth_headers(ADMIN), **overrides).status_code == 422


def test_each_new_account_gets_a_different_password(
    api_client: TestClient, auth_headers: Headers
) -> None:
    headers = auth_headers(ADMIN)

    first = create(api_client, headers, email="a1@example.com").json()["temporary_password"]
    second = create(api_client, headers, email="a2@example.com").json()["temporary_password"]

    assert first != second


# --- Sửa, khoá, vai trò --------------------------------------------------------------------------


def test_update_changes_only_the_fields_sent(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    target = user_id(db_session, "gv.van.11@example.com")

    response = api_client.patch(
        f"{API}/admin/users/{target}",
        headers=headers,
        json={"full_name": "Nguyễn Văn Đổi Tên", "email": "Van.Moi@Example.com"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Nguyễn Văn Đổi Tên"
    assert body["email"] == "van.moi@example.com"
    assert body["role"] == "teacher"
    assert body["is_active"] is True
    assert body["assignment_count"] > 0  # phân công giữ nguyên
    logged = audit_rows(db_session, AuditAction.UPDATE_USER)
    assert logged[0].details == {"user_id": target, "fields": ["email", "full_name"]}


@pytest.mark.parametrize("body", [{}, {"full_name": None}, {"is_active": None}, {"role": "x"}])
def test_update_rejects_empty_null_or_unknown_values(
    api_client: TestClient, auth_headers: Headers, db_session: Session, body: dict[str, Any]
) -> None:
    target = user_id(db_session, "gv.van.11@example.com")

    response = api_client.patch(
        f"{API}/admin/users/{target}", headers=auth_headers(ADMIN), json=body
    )

    assert response.status_code == 422


def test_update_rejects_an_email_used_by_someone_else_but_allows_keeping_your_own(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    target = user_id(db_session, "gv.van.11@example.com")

    clash = api_client.patch(
        f"{API}/admin/users/{target}", headers=headers, json={"email": "BGH1@example.com"}
    )
    same = api_client.patch(
        f"{API}/admin/users/{target}", headers=headers, json={"email": "GV.VAN.11@example.com"}
    )

    assert clash.status_code == 409
    assert same.status_code == 200


def test_locking_blocks_login_and_the_open_session_at_once_and_unlocking_restores_it(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    admin = auth_headers(ADMIN)
    target = user_id(db_session, "gv.toan.11@example.com")
    teacher = auth_headers("gv.toan.11@example.com")
    assert api_client.get(f"{API}/me/assignments", headers=teacher).status_code == 200

    locked = api_client.patch(
        f"{API}/admin/users/{target}", headers=admin, json={"is_active": False}
    )

    assert locked.status_code == 200
    assert locked.json()["is_active"] is False
    assert api_client.get(f"{API}/me/assignments", headers=teacher).status_code == 401
    assert login(api_client, "gv.toan.11@example.com", DEV_PASSWORD).status_code == 401
    logged = audit_rows(db_session, AuditAction.UPDATE_USER)
    assert logged[0].details["is_active"] == [True, False]

    unlocked = api_client.patch(
        f"{API}/admin/users/{target}", headers=admin, json={"is_active": True}
    )
    assert unlocked.status_code == 200
    assert api_client.get(f"{API}/me/assignments", headers=teacher).status_code == 200
    assert login(api_client, "gv.toan.11@example.com", DEV_PASSWORD).status_code == 200


def test_an_admin_cannot_lock_or_demote_their_own_account(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    me = user_id(db_session, ADMIN)

    for body in ({"is_active": False}, {"role": "teacher"}, {"role": "principal"}):
        response = api_client.patch(f"{API}/admin/users/{me}", headers=headers, json=body)
        assert response.status_code == 409, body

    # Vẫn sửa được tên của chính mình, và còn là Admin hoạt động.
    ok = api_client.patch(f"{API}/admin/users/{me}", headers=headers, json={"full_name": "Giáo vụ"})
    assert ok.status_code == 200
    assert ok.json()["role"] == "admin" and ok.json()["is_active"] is True


def test_a_second_admin_can_lock_the_first_but_never_the_last_one_left(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    created = create(api_client, headers, email="admin2@example.com", role="admin").json()
    second = {"Authorization": f"Bearer {create_access_token(created['user']['id'])[0]}"}
    first = user_id(db_session, ADMIN)

    # Admin thứ hai khoá Admin thứ nhất: được. Khi đó Admin thứ hai là người cuối, không tự khoá.
    assert (
        api_client.patch(
            f"{API}/admin/users/{first}", headers=second, json={"is_active": False}
        ).status_code
        == 200
    )
    assert (
        api_client.patch(
            f"{API}/admin/users/{created['user']['id']}", headers=second, json={"is_active": False}
        ).status_code
        == 409
    )
    assert api_client.get(f"{API}/admin/users", headers=headers).status_code == 401  # đã bị khoá


def test_role_change_is_refused_while_the_teacher_has_classes_or_assignments(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    homeroom = user_id(db_session, "gvcn.11a2@example.com")
    subject_teacher = user_id(db_session, "gv.van.11@example.com")

    for target in (homeroom, subject_teacher):
        response = api_client.patch(
            f"{API}/admin/users/{target}", headers=headers, json={"role": "principal"}
        )
        assert response.status_code == 409
        assert "phân công" in response.json()["detail"]
    assert db_session.get(User, homeroom).role.value == "teacher"  # type: ignore[union-attr]


def test_a_teacher_without_duties_can_become_principal_and_back(
    api_client: TestClient, auth_headers: Headers
) -> None:
    headers = auth_headers(ADMIN)
    created = create(api_client, headers).json()["user"]

    up = api_client.patch(
        f"{API}/admin/users/{created['id']}", headers=headers, json={"role": "principal"}
    )
    back = api_client.patch(
        f"{API}/admin/users/{created['id']}", headers=headers, json={"role": "teacher"}
    )

    assert up.status_code == 200 and up.json()["role_label"] == "Ban giám hiệu"
    assert back.status_code == 200 and back.json()["role"] == "teacher"


def test_update_and_reset_return_404_for_an_unknown_account(
    api_client: TestClient, auth_headers: Headers
) -> None:
    headers = auth_headers(ADMIN)

    assert (
        api_client.patch(f"{API}/admin/users/999999", headers=headers, json={"is_active": False})
    ).status_code == 404
    assert (
        api_client.post(f"{API}/admin/users/999999/reset-password", headers=headers).status_code
        == 404
    )


# --- Đặt lại mật khẩu -----------------------------------------------------------------------------


def test_reset_replaces_the_password_and_logs_without_the_secret(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    target = user_id(db_session, "gv.van.11@example.com")

    response = api_client.post(
        f"{API}/admin/users/{target}/reset-password", headers=auth_headers(ADMIN)
    )

    assert response.status_code == 200
    password = response.json()["temporary_password"]
    assert len(password) == 12
    assert login(api_client, "gv.van.11@example.com", password).status_code == 200
    assert login(api_client, "gv.van.11@example.com", DEV_PASSWORD).status_code == 401
    logged = audit_rows(db_session, AuditAction.RESET_USER_PASSWORD)
    assert logged[0].details == {"user_id": target}
    assert password not in str([row.details for row in db_session.scalars(select(AuditLog))])


# --- Tự đổi mật khẩu (mọi vai trò) ----------------------------------------------------------------


def change(client: TestClient, headers: dict[str, str], current: str, new: str) -> Response:
    return client.post(
        f"{API}/auth/change-password",
        headers=headers,
        json={"current_password": current, "new_password": new},
    )


@pytest.mark.parametrize("email", [ADMIN, *NON_ADMINS])
def test_every_role_can_change_their_own_password(
    api_client: TestClient, auth_headers: Headers, db_session: Session, email: str
) -> None:
    response = change(api_client, auth_headers(email), DEV_PASSWORD, "Mat-khau-moi-123")

    assert response.status_code == 200
    assert login(api_client, email, "Mat-khau-moi-123").status_code == 200
    assert login(api_client, email, DEV_PASSWORD).status_code == 401
    logged = audit_rows(db_session, AuditAction.CHANGE_PASSWORD)
    assert [row.user_id for row in logged] == [user_id(db_session, email)]
    assert logged[0].details == {}


@pytest.mark.parametrize(
    ("current", "new", "expected", "message"),
    [
        ("sai-mat-khau", "Mat-khau-moi-123", 400, "hiện tại không đúng"),
        (DEV_PASSWORD, DEV_PASSWORD, 400, "khác mật khẩu hiện tại"),
        (DEV_PASSWORD, "ngan", 422, None),
        (DEV_PASSWORD, "a" * 73, 422, None),
        (DEV_PASSWORD, "ế" * 25, 422, None),  # 25 ký tự nhưng 75 byte UTF-8
    ],
)
def test_change_password_refuses_bad_input_and_changes_nothing(
    api_client: TestClient,
    auth_headers: Headers,
    current: str,
    new: str,
    expected: int,
    message: str | None,
) -> None:
    response = change(api_client, auth_headers("gv.van.11@example.com"), current, new)

    assert response.status_code == expected
    if message:
        assert message in response.json()["detail"]
    assert login(api_client, "gv.van.11@example.com", DEV_PASSWORD).status_code == 200


def test_change_password_needs_a_login(api_client: TestClient) -> None:
    response = api_client.post(
        f"{API}/auth/change-password",
        json={"current_password": DEV_PASSWORD, "new_password": "Mat-khau-moi-123"},
    )

    assert response.status_code == 401

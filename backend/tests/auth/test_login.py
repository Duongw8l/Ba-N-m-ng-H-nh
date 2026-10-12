"""POST /auth/login với bcrypt thật (chậm nên ít ca) và dùng token nhận được."""

import pytest
from fastapi.testclient import TestClient

from app.auth.tokens import decode_access_token
from data.seed.people import DEV_PASSWORD

pytestmark = pytest.mark.db

WRONG_CREDENTIALS = "Email hoặc mật khẩu không đúng."


def login(client: TestClient, email: str, password: str):  # noqa: ANN201
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_login_returns_a_usable_token_and_the_user_without_password_hash(
    api_client: TestClient,
) -> None:
    response = login(api_client, "gv.toan.10@example.com", DEV_PASSWORD)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "token_type", "expires_in", "user"}
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 7200
    assert set(body["user"]) == {"id", "email", "full_name", "role"}
    assert body["user"]["role"] == "teacher"
    assert "password" not in response.text
    assert decode_access_token(body["access_token"]) == body["user"]["id"]

    me = api_client.get(
        "/api/v1/me/assignments", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["user"] == body["user"]


@pytest.mark.parametrize(
    ("email", "role"),
    [
        ("admin@example.com", "admin"),
        ("bgh1@example.com", "principal"),
        ("gvcn.10a2@example.com", "teacher"),
        ("gv.dia.10@example.com", "teacher"),
    ],
)
def test_every_seed_role_can_log_in(api_client: TestClient, email: str, role: str) -> None:
    response = login(api_client, email, DEV_PASSWORD)

    assert response.status_code == 200
    assert response.json()["user"]["role"] == role


def test_wrong_password_and_unknown_email_get_the_same_401(api_client: TestClient) -> None:
    wrong_password = login(api_client, "admin@example.com", "sai-mat-khau")
    unknown_email = login(api_client, "khong.co@example.com", DEV_PASSWORD)

    for response in (wrong_password, unknown_email):
        assert response.status_code == 401
        assert response.json() == {"detail": WRONG_CREDENTIALS}
        assert response.headers["www-authenticate"] == "Bearer"
        assert "access_token" not in response.text


def test_email_is_case_insensitive_and_trimmed(api_client: TestClient) -> None:
    response = login(api_client, "  Admin@Example.COM ", DEV_PASSWORD)

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "admin@example.com"


def test_password_longer_than_72_bytes_is_a_plain_401_not_a_server_error(
    api_client: TestClient,
) -> None:
    response = login(api_client, "admin@example.com", "a" * 100)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "body",
    [{}, {"email": "admin@example.com"}, {"password": "x"}, {"email": "", "password": "x"}],
    ids=["rong", "thieu-mat-khau", "thieu-email", "email-rong"],
)
def test_malformed_login_request_is_rejected_with_422(
    api_client: TestClient, body: dict[str, str]
) -> None:
    response = api_client.post("/api/v1/auth/login", json=body)

    assert response.status_code == 422

"""Tài khoản bị khoá (users.is_active = false, D-096): không đăng nhập, token cũ nhận 401 ngay."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.auth.models import User
from data.seed.people import DEV_PASSWORD

pytestmark = pytest.mark.db

EMAIL = "gv.toan.10@example.com"


def lock(session: Session, email: str) -> None:
    session.execute(
        update(User).where(func.lower(User.email) == email.lower()).values(is_active=False)
    )


def test_a_locked_account_cannot_log_in_and_gets_the_generic_401(
    api_client: TestClient, db_session: Session
) -> None:
    lock(db_session, EMAIL)

    locked = api_client.post("/api/v1/auth/login", json={"email": EMAIL, "password": DEV_PASSWORD})
    wrong = api_client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "sai-mat-khau"})

    assert locked.status_code == 401
    # Không báo riêng là "bị khoá": người ngoài không nên biết tài khoản có tồn tại.
    assert locked.json() == wrong.json()


def test_a_token_issued_before_locking_is_rejected_at_once(
    api_client: TestClient, db_session: Session, auth_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = auth_headers(EMAIL)
    assert api_client.get("/api/v1/me/assignments", headers=headers).status_code == 200

    lock(db_session, EMAIL)

    assert api_client.get("/api/v1/me/assignments", headers=headers).status_code == 401


def test_unlocking_restores_access(
    api_client: TestClient, db_session: Session, auth_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = auth_headers(EMAIL)
    lock(db_session, EMAIL)
    db_session.execute(
        update(User).where(func.lower(User.email) == EMAIL.lower()).values(is_active=True)
    )

    assert api_client.get("/api/v1/me/assignments", headers=headers).status_code == 200

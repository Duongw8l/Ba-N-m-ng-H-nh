import os

# Lấy URL DB thật (nếu có) TRƯỚC khi ghi đè bằng giá trị giả bên dưới, để test cần PostgreSQL thật
# (thư mục tests/db/) dùng database riêng "classroom_test" trên cùng máy chủ. Import config không
# khởi tạo Settings nên chưa đụng tới biến môi trường.
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.core.config import Settings

TEST_DATABASE_NAME = "classroom_test"


def _resolve_test_database_url() -> str | None:
    """TEST_DATABASE_URL nếu đặt (CI); không thì lấy DATABASE_URL thật rồi đổi tên DB."""
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    try:
        real_url = Settings().database_url  # type: ignore[call-arg]  # đọc từ môi trường / .env
    except ValidationError:
        return None
    return make_url(real_url).set(database=TEST_DATABASE_NAME).render_as_string(hide_password=False)


_TEST_DATABASE_URL = _resolve_test_database_url()

# Test không dùng DB hay khoá thật: đặt biến môi trường giả TRƯỚC khi import app,
# và ghi đè mọi giá trị đang có (kể cả trong .env của người chạy).
os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = "postgresql+psycopg://test:test@localhost:5432/test"
os.environ["JWT_SECRET"] = "chi-dung-trong-test"

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """URL của database dành riêng cho test có DB thật (tên phải kết thúc bằng _test)."""
    if _TEST_DATABASE_URL is None:
        pytest.exit(
            "Không xác định được database cho test. Tạo file .env (cp .env.example .env) hoặc "
            "đặt biến TEST_DATABASE_URL, rồi chạy make db.",
            returncode=1,
        )
    return _TEST_DATABASE_URL

import os

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

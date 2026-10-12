"""Fixture dùng chung cho mọi test.

Test không cần DB (ví dụ /health với Session giả) chạy độc lập. Test cần PostgreSQL thật có pgvector
(D-034, đánh dấu `pytest.mark.db`) dùng:
- `db_engine`: database "classroom_test" dựng bằng Alembic rồi seed mặc định (360 học sinh), dùng
  chung cả phiên test. Test không được sửa dữ liệu của nó: dùng `db_conn` hoặc `db_session`
  (luôn rollback).
- `fresh_database`: database tạm sạch, mỗi lần gọi một cái, cho test migration và seed lặp lại.
- `api_client`, `auth_headers`: gọi API thật trên `db_session` với token tạo trực tiếp.

Thiếu PostgreSQL thì dừng cả phiên bằng thông báo rõ ràng (không skip, để CI không lặng lẽ bỏ qua).
"""

import os

# Lấy URL DB thật (nếu có) TRƯỚC khi ghi đè bằng giá trị giả bên dưới, để test cần PostgreSQL thật
# dùng database riêng "classroom_test" trên cùng máy chủ. Import config không khởi tạo Settings nên
# chưa đụng tới biến môi trường.
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
os.environ["JWT_SECRET"] = "chi-dung-trong-test-khoa-bi-mat-dai-hon-32-ky-tu"  # từ 32 ký tự
os.environ["JWT_EXPIRE_MINUTES"] = "120"

import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, create_engine, func, select, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from alembic import command
from app.auth.models import User
from app.auth.tokens import create_access_token
from app.classes.models import SchoolClass, Subject
from app.core.db import get_db
from app.main import app
from data.seed.load import seed_database
from data.seed.params import SeedParams

BACKEND_DIR = Path(__file__).resolve().parents[1]
# Không có timeout thì kết nối tới cổng không ai lắng nghe (DB chưa bật) treo hơn 2 phút trên
# Windows.
CONNECT_ARGS = {"connect_timeout": 3}
NO_DB_MESSAGE = (
    "Không kết nối được PostgreSQL ở 127.0.0.1:5432. Chạy make db trước, rồi chạy lại make test "
    '(chỉ chạy test không cần DB: pytest -m "not db").'
)


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


# --- Database thật ----------------------------------------------------------------------------


def alembic_config(connection: Connection) -> Config:
    """Cấu hình Alembic dùng chung một connection (không phụ thuộc DATABASE_URL)."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


def upgrade(engine: Engine, revision: str = "head") -> None:
    with engine.begin() as connection:
        command.upgrade(alembic_config(connection), revision)


def downgrade(engine: Engine, revision: str = "base") -> None:
    with engine.begin() as connection:
        command.downgrade(alembic_config(connection), revision)


def _maintenance_engine(url: URL) -> Engine:
    # Kết nối vào DB "postgres" để tạo / xoá database test; CREATE DATABASE cần AUTOCOMMIT.
    return create_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
        connect_args=CONNECT_ARGS,
    )


def recreate_database(url: URL) -> None:
    """Xoá rồi tạo lại database test. Chỉ nhận tên kết thúc bằng _test, không đụng DB dev."""
    name = url.database or ""
    if not re.fullmatch(r"[a-z0-9_]+_test", name):
        pytest.exit(f"Từ chối xoá database '{name}': tên database test phải kết thúc bằng _test.")
    try:
        with _maintenance_engine(url).connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            connection.execute(text(f'CREATE DATABASE "{name}"'))
    except OperationalError:
        pytest.exit(NO_DB_MESSAGE, returncode=1)


def drop_database(url: URL) -> None:
    with _maintenance_engine(url).connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))


@pytest.fixture
def upgrade_db() -> Callable[[Engine], None]:
    return upgrade


@pytest.fixture
def downgrade_db() -> Callable[[Engine], None]:
    return downgrade


@pytest.fixture(scope="session")
def db_engine(test_database_url: str) -> Iterator[Engine]:
    url = make_url(test_database_url)
    recreate_database(url)
    engine = create_engine(url, pool_pre_ping=True, connect_args=CONNECT_ARGS)
    upgrade(engine)
    seed_database(engine, SeedParams())
    yield engine
    engine.dispose()  # giữ database lại để soi khi test lỗi; lần chạy sau tự dựng lại


@pytest.fixture
def db_conn(db_engine: Engine) -> Iterator[Connection]:
    """Một connection trong transaction luôn bị rollback: test thoải mái ghi vào DB dùng chung."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Session trên transaction ngoài luôn rollback. `join_transaction_mode="create_savepoint"`:
    app gọi session.commit() (ví dụ ghi nhật ký) thì chỉ là nhả savepoint, hết test vẫn sạch."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            autoflush=False,
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def fresh_database(test_database_url: str) -> Iterator[Callable[[], Engine]]:
    """Trả hàm tạo database tạm sạch (chưa migrate); tự xoá hết khi test xong."""
    created: list[tuple[Engine, URL]] = []
    base_url = make_url(test_database_url)

    def make() -> Engine:
        url = base_url.set(database=f"classroom_scratch{len(created)}_test")
        recreate_database(url)
        engine = create_engine(url, poolclass=NullPool, connect_args=CONNECT_ARGS)
        created.append((engine, url))
        return engine

    yield make
    for engine, url in created:
        engine.dispose()
        drop_database(url)


# --- API trên DB thật -------------------------------------------------------------------------


@pytest.fixture
def api_client(db_session: Session) -> Iterator[TestClient]:
    """TestClient gọi app thật, mọi request dùng `db_session`."""
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(db_session: Session) -> Callable[[str], dict[str, str]]:
    """Header Authorization cho một email trong dữ liệu seed. Tạo token trực tiếp (không qua
    /auth/login) để ma trận phân quyền khỏi tốn ~0,25 giây bcrypt mỗi lần."""

    def make(email: str) -> dict[str, str]:
        user_id = db_session.scalar(select(User.id).where(func.lower(User.email) == email.lower()))
        assert user_id is not None, f"Không có tài khoản seed {email}"
        token, _expires_in = create_access_token(user_id)
        return {"Authorization": f"Bearer {token}"}

    return make


@pytest.fixture
def subject_id_of(db_session: Session) -> Callable[[str], int]:
    """Id của môn theo tên (ví dụ "Toán") trong dữ liệu seed."""

    def find(name: str) -> int:
        subject_id = db_session.scalar(select(Subject.id).where(Subject.name == name))
        assert subject_id is not None, f"Không có môn seed {name}"
        return subject_id

    return find


@pytest.fixture
def class_id_of(db_session: Session) -> Callable[[str], int]:
    """Id của lớp theo tên (ví dụ "10A2") trong dữ liệu seed."""

    def find(name: str) -> int:
        class_id = db_session.scalar(select(SchoolClass.id).where(SchoolClass.name == name))
        assert class_id is not None, f"Không có lớp seed {name}"
        return class_id

    return find

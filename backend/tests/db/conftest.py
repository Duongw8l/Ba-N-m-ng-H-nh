"""Fixture cho test cần PostgreSQL thật có pgvector (D-034).

- `db_engine`: database "classroom_test" dựng bằng Alembic rồi seed mặc định (360 học sinh), dùng
  chung cả phiên test. Test không được sửa dữ liệu của nó: dùng `db_conn` (tự rollback).
- `fresh_database`: database tạm sạch, mỗi lần gọi một cái, cho test migration và seed lặp lại.

Thiếu PostgreSQL thì dừng cả phiên bằng thông báo rõ ràng (không skip, để CI không lặng lẽ bỏ qua).
"""

import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool

from alembic import command
from data.seed.load import seed_database
from data.seed.params import SeedParams

BACKEND_DIR = Path(__file__).resolve().parents[2]
# Không có timeout thì kết nối tới cổng không ai lắng nghe (DB chưa bật) treo hơn 2 phút trên
# Windows.
CONNECT_ARGS = {"connect_timeout": 3}
NO_DB_MESSAGE = (
    "Không kết nối được PostgreSQL ở 127.0.0.1:5432. Chạy make db trước, rồi chạy lại make test "
    '(chỉ chạy test không cần DB: pytest -m "not db").'
)


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

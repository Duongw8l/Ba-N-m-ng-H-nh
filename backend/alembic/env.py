"""Môi trường chạy migration của Alembic.

URL kết nối lấy từ Settings (biến DATABASE_URL), không ghi trong alembic.ini.
Mọi thay đổi schema DB phải đi qua migration (xem CLAUDE.md, mục Quy ước).

Test truyền sẵn một connection qua `config.attributes["connection"]` (cách làm chuẩn của Alembic
để chia sẻ connection), nên không phụ thuộc DATABASE_URL.
"""

from logging.config import fileConfig

from sqlalchemy import Connection, create_engine, pool

import app.models  # noqa: F401  (import để đăng ký mọi model vào Base.metadata)
from alembic import context
from app.core.base import Base
from app.core.config import get_settings

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False: không làm câm logger của pytest khi test gọi Alembic.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Sinh SQL mà không kết nối DB (alembic upgrade head --sql)."""
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def _run_with_connection(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Chạy migration trực tiếp trên DB."""
    shared_connection = config.attributes.get("connection")
    if shared_connection is not None:
        _run_with_connection(shared_connection)
        return

    connectable = create_engine(get_settings().database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        _run_with_connection(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

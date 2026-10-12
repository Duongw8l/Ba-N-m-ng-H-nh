"""Kết nối PostgreSQL bằng SQLAlchemy 2.0 (đồng bộ). Engine được tạo lười, lần đầu cần dùng."""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    # pool_pre_ping: tự bỏ kết nối chết (ví dụ sau khi DB khởi động lại).
    # connect_timeout (giây, tính cho mỗi địa chỉ): DB không với tới được thì báo lỗi sau vài giây,
    # không treo cả phút. Mạng Docker nội bộ kết nối trong mili giây nên 3 giây là dư dả.
    return create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3},
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependency của FastAPI: một Session cho mỗi request, tự đóng khi xong."""
    with get_session_factory()() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]

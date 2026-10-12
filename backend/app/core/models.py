"""Model dùng chung: bảng cấu hình `settings` (hệ số và ngưỡng, nguyên tắc 2 của CLAUDE.md)."""

from typing import Any

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


class Setting(Base):
    """Chỉ lưu giá trị. Công thức Thông tư 22 nằm trong app/analytics/, không nằm ở đây."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
    description: Mapped[str | None] = mapped_column(Text)

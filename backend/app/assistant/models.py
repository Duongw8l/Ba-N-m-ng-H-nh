"""Nhật ký hỏi đáp của trợ lý AI. Giai đoạn 8 ghi; Giai đoạn 1 chỉ tạo schema."""

from typing import Any

from sqlalchemy import ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, IntPk


class AiLog(Base):
    __tablename__ = "ai_logs"

    id: Mapped[IntPk]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    # Danh sách hàm Analytics đã gọi, kèm tham số.
    tools_called: Mapped[Any] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    answer: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    feedback: Mapped[str | None] = mapped_column(Text)

"""Nhật ký hỏi đáp của trợ lý AI (Giai đoạn 8, D-091).

`question` và `answer` lưu bản ĐÃ ẨN DANH (HS_01...), nên nhật ký không chứa họ tên học sinh; mã tạm
chỉ có nghĩa trong một request, không có bảng giải mã.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, IntPk, enum_type
from app.core.enums import AssistantFeedback


class AiLog(Base):
    __tablename__ = "ai_logs"
    __table_args__ = (
        # Giới hạn số câu hỏi mỗi phút: đếm dòng của một tài khoản trong 60 giây gần nhất.
        Index("ix_ai_logs_user_created", "user_id", "created_at"),
    )

    id: Mapped[IntPk]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    question: Mapped[str] = mapped_column(Text)
    # Các hàm đã gọi: [{"name", "args", "ok", "blocked", "ms"}]; args chỉ chứa mã tạm.
    tools_called: Mapped[Any] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    answer: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    feedback: Mapped[AssistantFeedback | None] = mapped_column(
        enum_type(AssistantFeedback, "feedback")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    rounds: Mapped[int | None] = mapped_column(Integer)  # số vòng gọi hàm đã dùng
    error: Mapped[str | None] = mapped_column(Text)  # có giá trị khi gọi LLM thất bại

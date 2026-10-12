"""Cảnh báo sớm. Bảng này do Giai đoạn 6 ghi; Giai đoạn 1 chỉ tạo schema."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, IntPk, enum_type
from app.core.enums import RiskLevel, TeacherStatus


class RiskAlert(Base):
    __tablename__ = "risk_alerts"
    __table_args__ = (
        CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 1)", name="risk_score_range"
        ),
    )

    id: Mapped[IntPk]
    class_student_id: Mapped[int] = mapped_column(
        ForeignKey("class_students.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[RiskLevel] = mapped_column(enum_type(RiskLevel, "level"))
    # Xác suất 0..1 của mô hình ML; cảnh báo theo luật cứng có thể không có điểm.
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    # Lý do dạng JSON để giao diện và LLM giải thích được, ví dụ {"absent_days": 38}.
    reasons: Mapped[Any] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    model_version: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    teacher_status: Mapped[TeacherStatus] = mapped_column(
        enum_type(TeacherStatus, "teacher_status"), server_default=TeacherStatus.NEW.value
    )

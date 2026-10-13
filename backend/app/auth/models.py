"""Model người dùng và nhật ký truy cập. GVBM / GVCN không phải cột: suy ra từ
teaching_assignments và classes.homeroom_teacher_id (xem docs/DESIGN.md mục 2)."""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, IntPk, enum_type
from app.core.enums import AuditAction, UserRole


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Email không phân biệt hoa thường.
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
    )

    id: Mapped[IntPk]
    email: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[UserRole] = mapped_column(enum_type(UserRole, "role"))
    # Tài khoản bị khoá không đăng nhập được và token cũ nhận 401 ngay (D-096); không xoá tài khoản
    # vì điểm, nhật ký, phân công còn tham chiếu tới người dùng.
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class AuditLog(Base):
    """Nhật ký mỗi lần ai đó mở dữ liệu học sinh (DESIGN mục 10). Chỉ thêm, không sửa.

    `class_id` là số nguyên thường, không có khoá ngoại, để nhật ký còn lại khi lớp bị xoá.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_class_id", "class_id"),
    )

    id: Mapped[IntPk]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[AuditAction] = mapped_column(enum_type(AuditAction, "action"))
    class_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[Any] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

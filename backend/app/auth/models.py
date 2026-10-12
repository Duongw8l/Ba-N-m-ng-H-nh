"""Model người dùng. GVBM / GVCN không phải cột: suy ra từ teaching_assignments và
classes.homeroom_teacher_id (xem docs/DESIGN.md mục 2)."""

from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, IntPk, enum_type
from app.core.enums import UserRole


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

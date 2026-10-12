"""Ghi nhật ký truy cập dữ liệu học sinh (DESIGN mục 10)."""

from typing import Any

from sqlalchemy.orm import Session

from app.auth.models import AuditLog, User
from app.core.enums import AuditAction


def record_access(
    session: Session,
    user: User,
    action: AuditAction,
    *,
    class_id: int | None,
    details: dict[str, Any],
) -> None:
    """Ghi và commit NGAY. Gọi trước khi trả dữ liệu cho người dùng: ghi lỗi thì request lỗi,
    không bao giờ trả dữ liệu mà không có nhật ký."""
    session.add(AuditLog(user_id=user.id, action=action, class_id=class_id, details=details))
    session.commit()

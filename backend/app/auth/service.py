"""Xác thực email và mật khẩu."""

from functools import lru_cache

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.security import hash_password, verify_password


@lru_cache
def _dummy_hash() -> str:
    # Hash không thuộc về ai, chỉ để tốn đúng thời gian của một lần kiểm bcrypt.
    return hash_password("mat-khau-gia-khong-ai-dung")


def authenticate(session: Session, email: str, password: str) -> User | None:
    """Trả người dùng nếu đúng email và mật khẩu, không thì None.

    Email không tồn tại vẫn chạy một lần verify_password với hash giả, để thời gian phản hồi không
    cho biết email nào có trong hệ thống. Email so khớp không phân biệt hoa thường. Tài khoản bị
    khoá (D-096) bị từ chối như sai mật khẩu, không báo riêng là bị khoá.
    """
    user = session.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    password_ok = verify_password(password, user.password_hash if user else _dummy_hash())
    return user if user is not None and user.is_active and password_ok else None

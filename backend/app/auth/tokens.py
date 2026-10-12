"""Tạo và kiểm tra access token (JWT, HS256, PyJWT).

Token chỉ chứa id người dùng (`sub`) và thời hạn. Vai trò KHÔNG nằm trong token: mỗi request nạp
lại người dùng từ DB, nên đổi vai trò hay xoá tài khoản có hiệu lực ngay (D-041).
"""

from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings

ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    """Token sai chữ ký, hỏng, hết hạn hoặc thiếu thông tin."""


def create_access_token(user_id: int, *, now: datetime | None = None) -> tuple[str, int]:
    """Trả (token, số giây còn hiệu lực). `now` chỉ để test."""
    settings = get_settings()
    issued_at = now or datetime.now(UTC)
    expires_in = settings.jwt_expire_minutes * 60
    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": issued_at + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)
    return token, expires_in


def decode_access_token(token: str) -> int:
    """Trả id người dùng hoặc ném InvalidTokenError. Luôn chỉ định thuật toán (chặn alg=none)."""
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        return int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as error:
        raise InvalidTokenError from error

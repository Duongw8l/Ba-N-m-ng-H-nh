"""Dependency xác thực của FastAPI: lấy người dùng hiện tại từ header Authorization: Bearer."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.models import User
from app.auth.tokens import InvalidTokenError, decode_access_token
from app.core.db import DbSession

# auto_error=False để tự trả 401 (HTTPBearer mặc định trả mã khác khi thiếu header).
_bearer = HTTPBearer(auto_error=False, description="Dán access token lấy từ POST /auth/login.")


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Cần đăng nhập.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise _unauthenticated()
    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise _unauthenticated() from None
    # Nạp lại mỗi request: đổi vai trò hay xoá tài khoản có hiệu lực ngay.
    user = session.get(User, user_id)
    if user is None:
        raise _unauthenticated()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

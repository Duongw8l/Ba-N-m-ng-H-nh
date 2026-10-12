"""POST /api/v1/auth/login.

NGOẠI LỆ nguyên tắc 4 của CLAUDE.md: endpoint công khai, không qua authorize() vì chưa có phiên.
Chỉ trả token và thông tin của chính người đăng nhập. Xem docs/DECISIONS.md (D-042).
"""

from fastapi import APIRouter, HTTPException, status

from app.auth.schemas import LoginRequest, LoginResponse, UserOut
from app.auth.service import authenticate
from app.auth.tokens import create_access_token
from app.core.db import DbSession

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse, summary="Đăng nhập, trả JWT")
def login(body: LoginRequest, session: DbSession) -> LoginResponse:
    user = authenticate(session, body.email, body.password)
    if user is None:
        # Cùng một thông điệp cho email lạ và mật khẩu sai.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_in = create_access_token(user.id)
    return LoginResponse(
        access_token=token, expires_in=expires_in, user=UserOut.model_validate(user)
    )

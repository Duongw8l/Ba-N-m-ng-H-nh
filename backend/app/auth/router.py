"""POST /api/v1/auth/login và POST /api/v1/auth/change-password.

NGOẠI LỆ nguyên tắc 4 của CLAUDE.md: `login` công khai, không qua authorize() vì chưa có phiên;
chỉ trả token và thông tin của chính người đăng nhập (D-042). `change-password` chỉ đụng tài khoản
của chính người gọi, không có phạm vi lớp/môn nào để kiểm (D-097).
"""

from fastapi import APIRouter, HTTPException, status

from app.auth import admin_service
from app.auth.admin_schemas import ChangePasswordIn, MessageOut
from app.auth.deps import CurrentUser
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


@router.post(
    "/change-password",
    response_model=MessageOut,
    summary="Đổi mật khẩu của chính mình (mọi vai trò)",
)
def change_password(body: ChangePasswordIn, user: CurrentUser, session: DbSession) -> MessageOut:
    try:
        admin_service.change_password(session, user, body)
    except admin_service.WrongPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Mật khẩu hiện tại không đúng."
        ) from None
    except admin_service.PasswordUnchanged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu mới phải khác mật khẩu hiện tại.",
        ) from None
    return MessageOut(detail="Đã đổi mật khẩu.")

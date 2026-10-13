"""Quản lý tài khoản của Admin (D-096, D-097): chỉ Admin, qua `AdminUser` (401 rồi 403 trước tiên).

Admin không xem dữ liệu học sinh (D-039): các endpoint này chỉ đụng bảng `users`.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.auth import admin_service as service
from app.auth.admin_schemas import (
    AdminUserOut,
    CreatedUserOut,
    PasswordResetOut,
    UserCreateIn,
    UserUpdateIn,
)
from app.auth.deps import AdminUser
from app.core.db import DbSession
from app.core.enums import UserRole

router = APIRouter(prefix="/admin/users", tags=["admin"])

NOT_FOUND = "Không có tài khoản này."


@router.get("", response_model=list[AdminUserOut], summary="Danh sách tài khoản (chỉ Admin)")
def list_users(
    admin: AdminUser,
    session: DbSession,
    role: Annotated[UserRole | None, Query(description="Lọc theo vai trò")] = None,
    active: Annotated[
        bool | None, Query(description="true: đang hoạt động; false: bị khoá")
    ] = None,
    q: Annotated[str | None, Query(max_length=100, description="Tìm theo tên hoặc email")] = None,
) -> list[AdminUserOut]:
    return service.list_users(session, role=role, active=active, query=q)


@router.post(
    "",
    response_model=CreatedUserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo tài khoản, trả mật khẩu tạm một lần (chỉ Admin)",
)
def create_user(admin: AdminUser, session: DbSession, body: UserCreateIn) -> CreatedUserOut:
    try:
        return service.create_user(session, admin, body)
    except service.EmailTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email này đã có tài khoản.") from None


@router.patch(
    "/{user_id}",
    response_model=AdminUserOut,
    summary="Sửa tên, email, vai trò, khoá hoặc mở khoá tài khoản (chỉ Admin)",
)
def update_user(
    user_id: int, admin: AdminUser, session: DbSession, body: UserUpdateIn
) -> AdminUserOut:
    try:
        return service.update_user(session, admin, user_id, body)
    except service.UserNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND) from None
    except service.EmailTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email này đã có tài khoản.") from None
    except service.SelfProtected:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Không thể khoá hoặc hạ quyền chính tài khoản đang đăng nhập.",
        ) from None
    except service.HasAssignments:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                "Giáo viên này đang chủ nhiệm hoặc được phân công giảng dạy. "
                "Hãy gỡ chủ nhiệm và phân công trước khi đổi vai trò."
            ),
        ) from None


@router.post(
    "/{user_id}/reset-password",
    response_model=PasswordResetOut,
    summary="Đặt lại mật khẩu, trả mật khẩu tạm một lần (chỉ Admin)",
)
def reset_password(user_id: int, admin: AdminUser, session: DbSession) -> PasswordResetOut:
    try:
        return service.reset_password(session, admin, user_id)
    except service.UserNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND) from None

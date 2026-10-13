"""Schema của API quản lý tài khoản (Admin) và đổi mật khẩu. Không schema nào có password_hash."""

from typing import Annotated, Self

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from app.core.enums import UserRole
from app.core.security import MAX_PASSWORD_BYTES

# Kiểm hình dạng đơn giản, không thêm thư viện email-validator: một @ và có dấu chấm ở tên miền.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
Email = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=255, pattern=EMAIL_PATTERN)
]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

MIN_PASSWORD_LENGTH = 8


class AdminUserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    role_label: str
    is_active: bool
    homeroom_class: str | None  # tên lớp đang chủ nhiệm
    assignment_count: int  # số cặp lớp-môn được phân công


class UserCreateIn(BaseModel):
    email: Email
    full_name: FullName
    role: UserRole


class UserUpdateIn(BaseModel):
    """Chỉ các trường có gửi lên mới đổi (`model_fields_set`)."""

    email: Email | None = None
    full_name: FullName | None = None
    role: UserRole | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _no_null_values(self) -> Self:
        # null nghĩa là "không đổi" chứ không phải xoá giá trị; gửi null tường minh là nhầm lẫn.
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"'{name}' không được để trống.")
        if not self.model_fields_set:
            raise ValueError("Không có trường nào để đổi.")
        return self


class CreatedUserOut(BaseModel):
    user: AdminUserOut
    # Bản rõ chỉ có trong phản hồi này; không lưu ở đâu khác và không ghi nhật ký.
    temporary_password: str


class PasswordResetOut(BaseModel):
    temporary_password: str


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _within_bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"Mật khẩu mới dài quá {MAX_PASSWORD_BYTES} byte.")
        return value


class MessageOut(BaseModel):
    detail: str

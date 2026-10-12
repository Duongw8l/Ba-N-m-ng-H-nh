from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import UserRole


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    """Thông tin người dùng đưa ra ngoài. Không bao giờ có password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: UserRole


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # số giây token còn hiệu lực
    user: UserOut

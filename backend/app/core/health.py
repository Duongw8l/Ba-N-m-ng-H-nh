"""GET /api/v1/health: kiểm tra API còn sống và kết nối được tới DB.

NGOẠI LỆ nguyên tắc 4 của CLAUDE.md: đây là endpoint công khai, không qua authorize().
Lý do: trang chủ gọi nó trước khi đăng nhập và Docker healthcheck không có token.
Vì vậy nó chỉ trả trạng thái, không bao giờ trả dữ liệu học sinh hay chi tiết lỗi.
Xem docs/DECISIONS.md (D-001).
"""

import logging
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import DbSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    db: bool


@router.get("/health", response_model=HealthResponse, summary="Kiểm tra tình trạng hệ thống")
def health(session: DbSession) -> HealthResponse:
    # Luôn trả HTTP 200: "status" cho biết API còn sống, "db" cho biết kết nối DB.
    try:
        session.execute(text("SELECT 1"))
        db_ok = True
    except SQLAlchemyError as exc:
        # Chỉ ghi log phía máy chủ, không đưa chi tiết lỗi ra response. Một dòng, không traceback:
        # endpoint này bị gọi dồn dập (Docker healthcheck 10 giây một lần, mỗi tab 15 giây).
        logger.warning("Không kết nối được tới cơ sở dữ liệu: %s", exc)
        db_ok = False
    return HealthResponse(status="ok", db=db_ok)

"""Văn bản quy định cho RAG.

Giai đoạn 1 chỉ tạo cột vector; nạp văn bản và tính vector ở Giai đoạn 7.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, IntPk
from app.core.config import get_settings

# Số chiều lấy từ cấu hình lúc import. Đã cố định vào cột khi chạy migration; đổi về sau cần
# migration mới (xem comment ở core/config.py).
EMBEDDING_DIM = get_settings().embedding_dim


class RegulationChunk(Base):
    __tablename__ = "regulation_chunks"

    id: Mapped[IntPk]
    document_name: Mapped[str] = mapped_column(String(200))
    article: Mapped[str | None] = mapped_column(String(100))
    clause: Mapped[str | None] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    # NULL cho tới khi tính vector (nạp chữ trước, vector sau).
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))

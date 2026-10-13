"""Văn bản quy định cho RAG (Giai đoạn 7, D-076).

`regulation_documents`: một dòng mỗi văn bản (tên, tệp, hiệu lực). `regulation_chunks`: các đoạn đã
tách theo Điều/Khoản kèm vector. RAG chỉ trích đoạn của văn bản còn hiệu lực.

Cả hai bảng nằm trong KEPT_TABLES của seed (D-036): nạp văn bản và tính vector tốn công. Vì
`make seed` chạy TRUNCATE users ... CASCADE nên `uploaded_by` KHÔNG có khoá ngoại tới users (khoá
ngoại sẽ kéo theo xoá luôn văn bản đã nạp).
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, IntPk, enum_type
from app.core.config import get_settings
from app.core.enums import RegulationStatus

# Số chiều lấy từ cấu hình lúc import. Đã cố định vào cột khi chạy migration; đổi về sau cần
# migration mới (xem comment ở core/config.py).
EMBEDDING_DIM = get_settings().embedding_dim


class RegulationDocument(Base):
    __tablename__ = "regulation_documents"
    __table_args__ = (
        # Mỗi tên chỉ có một bản còn hiệu lực: bản mới thay bản cũ thì phải đánh dấu bản cũ là
        # hết hiệu lực trước.
        Index(
            "uq_regulation_documents_active_name",
            "name",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[IntPk]
    # Tên hiển thị trong trích dẫn, ví dụ "Thông tư 22/2021/TT-BGDĐT".
    name: Mapped[str] = mapped_column(String(200))
    file_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[RegulationStatus] = mapped_column(
        enum_type(RegulationStatus, "status"), server_default=RegulationStatus.ACTIVE.value
    )
    uploaded_by: Mapped[int | None]  # id người dùng (không khoá ngoại, xem docstring của module)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RegulationChunk(Base):
    __tablename__ = "regulation_chunks"
    __table_args__ = (
        # Tìm láng giềng gần nhất theo cosine (toán tử <=>).
        Index(
            "ix_regulation_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[IntPk]
    document_id: Mapped[int] = mapped_column(
        ForeignKey("regulation_documents.id", ondelete="CASCADE"), index=True
    )
    document_name: Mapped[str] = mapped_column(String(200))
    article: Mapped[str | None] = mapped_column(String(100))  # ví dụ "Điều 12"
    clause: Mapped[str | None] = mapped_column(String(100))  # ví dụ "Khoản 1", "Khoản 1, điểm a"
    content: Mapped[str] = mapped_column(Text)
    # NULL cho tới khi tính vector (nạp chữ trước, vector sau).
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))

"""Schema request/response của API văn bản quy định."""

from datetime import datetime

from pydantic import BaseModel

from app.core.enums import RegulationStatus


class DocumentOut(BaseModel):
    id: int
    name: str
    file_name: str
    status: RegulationStatus
    status_label: str
    created_at: datetime
    expired_at: datetime | None
    article_count: int
    chunk_count: int


class DocumentStatusIn(BaseModel):
    status: RegulationStatus


class SearchHitOut(BaseModel):
    document_id: int
    document_name: str
    article: str | None
    clause: str | None
    content: str
    similarity: float


class SearchOut(BaseModel):
    found: bool
    message: str | None  # "Không tìm thấy trong văn bản quy định" khi found=False
    hits: list[SearchHitOut]
    best_similarity: float | None
    min_similarity: float

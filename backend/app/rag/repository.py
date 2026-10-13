"""Truy vấn bảng regulation_documents và regulation_chunks (Giai đoạn 7)."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, distinct, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.enums import RegulationStatus
from app.core.models import Setting
from app.rag.chunking import Chunk
from app.rag.models import RegulationChunk, RegulationDocument

SIMILARITY_KEY = "rag_min_similarity"


class MissingSimilaritySetting(RuntimeError):
    """Bảng settings chưa có ngưỡng tìm kiếm (chưa chạy migration?)."""


@dataclass(frozen=True)
class DocumentRow:
    document: RegulationDocument
    article_count: int
    chunk_count: int


def _document_rows_query() -> Select[tuple[RegulationDocument, int, int]]:
    articles = func.count(distinct(RegulationChunk.article)).filter(
        RegulationChunk.article.like("Điều%")
    )
    return (
        select(RegulationDocument, articles, func.count(RegulationChunk.id))
        .outerjoin(RegulationChunk, RegulationChunk.document_id == RegulationDocument.id)
        .group_by(RegulationDocument.id)
    )


def list_documents(session: Session) -> list[DocumentRow]:
    """Còn hiệu lực trước, trong mỗi nhóm thì mới tải lên trước."""
    query = _document_rows_query().order_by(
        RegulationDocument.status,
        RegulationDocument.created_at.desc(),
        RegulationDocument.id.desc(),
    )
    return [DocumentRow(doc, articles, chunks) for doc, articles, chunks in session.execute(query)]


def get_document_row(session: Session, document_id: int) -> DocumentRow | None:
    row = session.execute(
        _document_rows_query().where(RegulationDocument.id == document_id)
    ).one_or_none()
    return DocumentRow(*row) if row else None


def get_document(session: Session, document_id: int) -> RegulationDocument | None:
    return session.get(RegulationDocument, document_id)


def active_document_with_name(session: Session, name: str) -> RegulationDocument | None:
    return session.scalar(
        select(RegulationDocument).where(
            RegulationDocument.name == name, RegulationDocument.status == RegulationStatus.ACTIVE
        )
    )


def add_document(
    session: Session, *, name: str, file_name: str, uploaded_by: int | None
) -> RegulationDocument:
    document = RegulationDocument(name=name, file_name=file_name, uploaded_by=uploaded_by)
    session.add(document)
    session.flush()
    return document


def add_chunks(
    session: Session,
    document: RegulationDocument,
    chunks: list[Chunk],
    vectors: list[list[float]],
) -> None:
    session.add_all(
        RegulationChunk(
            document_id=document.id,
            document_name=document.name,
            article=chunk.article,
            clause=chunk.clause,
            content=chunk.content,
            embedding=vector,
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    )
    session.flush()


def set_status(
    session: Session, document: RegulationDocument, status: RegulationStatus, now: datetime
) -> None:
    document.status = status
    document.expired_at = now if status is RegulationStatus.EXPIRED else None
    session.flush()


def min_similarity(session: Session) -> float:
    value = session.scalar(select(Setting.value).where(Setting.key == SIMILARITY_KEY))
    if value is None:
        raise MissingSimilaritySetting(
            f"Bảng settings thiếu khoá {SIMILARITY_KEY}. Chạy make migrate."
        )
    return float(value)


def nearest_chunks(
    session: Session, vector: list[float], limit: int
) -> list[tuple[RegulationChunk, float]]:
    """`limit` đoạn gần nhất theo cosine, CHỈ trong văn bản còn hiệu lực. Trả (đoạn, khoảng cách).

    Lọc hiệu lực nằm ngay trong truy vấn, không lọc sau bằng Python, để văn bản hết hiệu lực không
    bao giờ rời khỏi DB.
    """
    _enable_iterative_scan(session)
    distance = RegulationChunk.embedding.cosine_distance(vector)
    query = (
        select(RegulationChunk, distance)
        .join(RegulationDocument, RegulationDocument.id == RegulationChunk.document_id)
        .where(
            RegulationDocument.status == RegulationStatus.ACTIVE,
            RegulationChunk.embedding.is_not(None),
        )
        .order_by(distance, RegulationChunk.id)
        .limit(limit)
    )
    return [(chunk, float(dist)) for chunk, dist in session.execute(query)]


def _enable_iterative_scan(session: Session) -> None:
    """Chỉ mục HNSW lấy ~40 láng giềng gần nhất rồi mới lọc theo hiệu lực; nếu bản cũ (hết hiệu
    lực) của cùng một văn bản chiếm hết 40 chỗ đó thì bản mới có thể bị bỏ sót. Quét lặp (pgvector
    từ 0.8) tiếp tục quét cho tới khi đủ kết quả sau lọc. Bản pgvector cũ không có: bỏ qua."""
    try:
        with session.begin_nested():
            session.execute(text("SET LOCAL hnsw.iterative_scan = strict_order"))
    except DBAPIError:
        pass

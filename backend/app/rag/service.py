"""Nạp văn bản quy định và đổi hiệu lực (Giai đoạn 7, D-080).

Nạp: đọc tệp, tách Điều/Khoản, tính vector (chưa đụng DB), rồi ghi văn bản + mọi đoạn + nhật ký
trong MỘT transaction: lỗi giữa chừng thì không còn gì lại. Tính vector tốn vài chục giây nên cố ý
làm trước khi mở transaction ghi.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.audit import record_access
from app.auth.models import User
from app.core.enums import AuditAction, RegulationStatus
from app.rag import repository as repo
from app.rag.chunking import Chunk, count_articles, split_into_chunks
from app.rag.embedding import Embedder
from app.rag.models import RegulationDocument
from app.rag.parsing import DocumentError, extract_text

# Giới hạn cho tải lên qua web: vector được tính ngay trong request. Văn bản lớn hơn thì nạp bằng
# make regulations (không giới hạn).
API_MAX_CHUNKS = 500
MAX_NAME_LENGTH = 200


class DuplicateDocument(Exception):
    """Đã có văn bản còn hiệu lực cùng tên."""

    def __init__(self, name: str) -> None:
        super().__init__(
            f'Đã có văn bản còn hiệu lực tên "{name}". Hãy đánh dấu bản cũ là hết hiệu lực trước '
            "khi tải bản mới."
        )


class DocumentNotFound(LookupError):
    pass


@dataclass(frozen=True)
class IngestResult:
    document: RegulationDocument
    article_count: int
    chunk_count: int


def embedding_text(document_name: str, chunk: Chunk) -> str:
    """Chữ đưa vào mô hình: kèm tên văn bản để câu hỏi nhắc tên văn bản vẫn tìm đúng."""
    return f"{document_name}\n{chunk.content}"


def ingest_document(
    session: Session,
    *,
    name: str,
    file_name: str,
    data: bytes,
    embedder: Embedder,
    user: User | None,
    max_chunks: int | None = API_MAX_CHUNKS,
) -> IngestResult:
    """Nạp một văn bản. `user` None (dòng lệnh) thì không ghi nhật ký người dùng."""
    name = " ".join(name.split())
    if not name:
        raise DocumentError("Cần đặt tên cho văn bản.")
    if len(name) > MAX_NAME_LENGTH:
        raise DocumentError(f"Tên văn bản dài quá {MAX_NAME_LENGTH} ký tự.")
    if repo.active_document_with_name(session, name) is not None:
        raise DuplicateDocument(name)

    chunks = split_into_chunks(extract_text(file_name, data))
    if not chunks:
        raise DocumentError(
            "Không tách được đoạn nào từ văn bản. Văn bản cần có các điều dạng "
            '"Điều 1. Tiêu đề" hoặc ít nhất vài đoạn chữ.'
        )
    if max_chunks is not None and len(chunks) > max_chunks:
        raise DocumentError(
            f"Văn bản có {len(chunks)} đoạn, quá {max_chunks}. Văn bản lớn hơn nên nạp bằng "
            "make regulations."
        )

    vectors = embedder.embed_passages([embedding_text(name, chunk) for chunk in chunks])
    if len(vectors) != len(chunks) or any(len(vector) != embedder.dim for vector in vectors):
        raise RuntimeError("Mô hình embedding trả số vector hoặc số chiều không khớp.")

    try:
        document = repo.add_document(
            session, name=name, file_name=file_name, uploaded_by=user.id if user else None
        )
        repo.add_chunks(session, document, chunks, vectors)
        if user is not None:
            record_access(
                session,
                user,
                AuditAction.UPLOAD_REGULATION,
                class_id=None,
                details={
                    "document_id": document.id,
                    "name": name,
                    "file_name": file_name,
                    "chunk_count": len(chunks),
                },
                commit=False,
            )
        session.commit()
    except IntegrityError as error:  # hai yêu cầu cùng tên cùng lúc: chỉ mục duy nhất từng phần
        session.rollback()
        raise DuplicateDocument(name) from error
    except Exception:
        session.rollback()
        raise
    return IngestResult(document, count_articles(chunks), len(chunks))


def change_status(
    session: Session, user: User, document_id: int, status: RegulationStatus
) -> repo.DocumentRow:
    """Đánh dấu hết hiệu lực / bật lại. Giá trị không đổi thì không làm gì và không ghi nhật ký."""
    document = repo.get_document(session, document_id)
    if document is None:
        raise DocumentNotFound(document_id)
    previous = document.status
    if previous is not status:
        if (
            status is RegulationStatus.ACTIVE
            and repo.active_document_with_name(session, document.name) is not None
        ):
            raise DuplicateDocument(document.name)
        try:
            repo.set_status(session, document, status, datetime.now(UTC))
            record_access(
                session,
                user,
                AuditAction.UPDATE_REGULATION,
                class_id=None,
                details={
                    "document_id": document.id,
                    "name": document.name,
                    "from": previous.value,
                    "to": status.value,
                },
                commit=False,
            )
            session.commit()
        except IntegrityError as error:
            session.rollback()
            raise DuplicateDocument(document.name) from error
        except Exception:
            session.rollback()
            raise
    row = repo.get_document_row(session, document_id)
    assert row is not None  # vừa lấy được ở trên
    return row

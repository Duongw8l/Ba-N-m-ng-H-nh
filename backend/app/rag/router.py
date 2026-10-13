"""API văn bản quy định (D-080): Admin quản lý, mọi người dùng đăng nhập được tìm.

- `/admin/regulations*`: chỉ Admin (authorize_admin chạy TRƯỚC khi đọc tệp tải lên hay dữ liệu).
- `GET /regulations/search`: mọi người dùng đã đăng nhập. Văn bản quy định là dữ liệu chung, không
  phải dữ liệu học sinh. Ngoài bảng API của DESIGN mục 7; dùng cho ô "Thử tìm" của Admin và eval.

Starlette nhận trọn thân multipart trước khi gọi hàm xử lý nên giới hạn dung lượng thật phải đặt
thêm ở reverse proxy (Giai đoạn 11); ở đây chỉ chặn khi đọc nội dung.
"""

from pathlib import PurePath
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.auth.deps import AdminUser, CurrentUser
from app.core.db import DbSession
from app.core.labels import label_vi
from app.rag import repository as repo
from app.rag import service
from app.rag.embedding import Embedder, EmbeddingUnavailable, get_embedder
from app.rag.parsing import MAX_FILE_BYTES, DocumentError, DocumentTooLarge
from app.rag.schemas import DocumentOut, DocumentStatusIn, SearchHitOut, SearchOut
from app.rag.search import DEFAULT_K, MAX_K, search_regulation

router = APIRouter(tags=["rag"])

MAX_QUERY_LENGTH = 500


def get_embedder_dependency() -> Embedder:
    """Dependency để test thay bằng bộ nhúng giả (app.dependency_overrides)."""
    return get_embedder()


EmbedderDep = Annotated[Embedder, Depends(get_embedder_dependency)]


def _document_out(row: repo.DocumentRow) -> DocumentOut:
    document = row.document
    return DocumentOut(
        id=document.id,
        name=document.name,
        file_name=document.file_name,
        status=document.status,
        status_label=label_vi(document.status),
        created_at=document.created_at,
        expired_at=document.expired_at,
        article_count=row.article_count,
        chunk_count=row.chunk_count,
    )


@router.get(
    "/admin/regulations",
    response_model=list[DocumentOut],
    summary="Danh sách văn bản quy định (chỉ Admin)",
)
def list_regulations(admin: AdminUser, session: DbSession) -> list[DocumentOut]:
    return [_document_out(row) for row in repo.list_documents(session)]


@router.post(
    "/admin/regulations",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Tải văn bản quy định (.pdf, .docx, .txt), tách Điều/Khoản và lưu (chỉ Admin)",
)
def upload_regulation(
    admin: AdminUser,
    session: DbSession,
    embedder: EmbedderDep,
    name: Annotated[str, Form(min_length=1, max_length=200, description="Tên hiển thị")],
    file: Annotated[UploadFile, File(description="Tệp .pdf, .docx hoặc .txt (UTF-8)")],
) -> DocumentOut:
    data = file.file.read(MAX_FILE_BYTES + 1)
    file_name = PurePath(file.filename or "tep").name  # chỉ tên tệp, bỏ mọi đường dẫn
    try:
        result = service.ingest_document(
            session, name=name, file_name=file_name, data=data, embedder=embedder, user=admin
        )
    except DocumentTooLarge as error:
        raise HTTPException(413, detail=str(error)) from error
    except DocumentError as error:
        raise HTTPException(422, detail=str(error)) from error
    except service.DuplicateDocument as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error
    except EmbeddingUnavailable as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error

    row = repo.DocumentRow(result.document, result.article_count, result.chunk_count)
    return _document_out(row)


@router.patch(
    "/admin/regulations/{document_id}",
    response_model=DocumentOut,
    summary="Đánh dấu hết hiệu lực hoặc bật lại một văn bản (chỉ Admin)",
)
def update_regulation(
    document_id: int, body: DocumentStatusIn, admin: AdminUser, session: DbSession
) -> DocumentOut:
    try:
        row = service.change_status(session, admin, document_id, body.status)
    except service.DocumentNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không có văn bản này.") from None
    except service.DuplicateDocument as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _document_out(row)


@router.get(
    "/regulations/search",
    response_model=SearchOut,
    summary="Tìm đoạn văn bản quy định còn hiệu lực liên quan tới câu hỏi",
)
def search(
    user: CurrentUser,
    session: DbSession,
    embedder: EmbedderDep,
    q: Annotated[str, Query(min_length=1, max_length=MAX_QUERY_LENGTH, description="Câu hỏi")],
    k: Annotated[int, Query(ge=1, le=MAX_K, description="Số đoạn tối đa")] = DEFAULT_K,
) -> SearchOut:
    if not q.strip():
        raise HTTPException(422, detail="Câu hỏi để trống.")
    try:
        result = search_regulation(session, q, k, embedder=embedder)
    except EmbeddingUnavailable as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    return SearchOut(
        found=result.found,
        message=result.message,
        hits=[
            SearchHitOut(
                document_id=hit.document_id,
                document_name=hit.document_name,
                article=hit.article,
                clause=hit.clause,
                content=hit.content,
                similarity=round(hit.similarity, 4),
            )
            for hit in result.hits
        ],
        best_similarity=None
        if result.best_similarity is None
        else round(result.best_similarity, 4),
        min_similarity=result.min_similarity,
    )

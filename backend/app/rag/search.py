"""search_regulation: tìm đoạn văn bản quy định liên quan tới câu hỏi (Giai đoạn 7, D-080).

Đây là hàm thứ 7 trong 7 hàm LLM được gọi (nguyên tắc 3, Giai đoạn 8 bọc lại). Văn bản quy định là
dữ liệu chung của trường, không phải dữ liệu học sinh nên không cần class_id/subject_id.

Hai điều bảo đảm:
- Chỉ tìm trong văn bản CÒN HIỆU LỰC (lọc ngay trong truy vấn SQL).
- Đoạn nào có độ tương đồng cosine dưới `settings.rag_min_similarity` thì bị bỏ. Không còn đoạn nào
  thì `found=False` và KHÔNG trả đoạn nào, để LLM không có gì để bịa ra "trích dẫn".
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.rag import repository as repo
from app.rag.embedding import Embedder, get_embedder

DEFAULT_K = 4
MAX_K = 10
NOT_FOUND_MESSAGE = "Không tìm thấy trong văn bản quy định"


@dataclass(frozen=True)
class SearchHit:
    document_id: int
    document_name: str
    article: str | None  # "Điều 12"
    clause: str | None  # "Khoản 1", "Khoản 1, điểm a"
    content: str
    similarity: float  # cosine, 0 đến 1 (càng cao càng liên quan)


@dataclass(frozen=True)
class SearchResult:
    found: bool
    message: str | None  # NOT_FOUND_MESSAGE khi found=False
    hits: list[SearchHit]  # rỗng khi found=False
    best_similarity: float | None  # của đoạn tốt nhất trong văn bản hiệu lực (kể cả khi bị loại)
    min_similarity: float  # ngưỡng đang dùng


def search_regulation(
    session: Session, query: str, k: int = DEFAULT_K, *, embedder: Embedder | None = None
) -> SearchResult:
    """Tối đa `k` đoạn liên quan nhất, sắp theo độ tương đồng giảm dần."""
    query = " ".join(query.split())
    if not query:
        raise ValueError("Câu hỏi không được để trống.")
    k = max(1, min(k, MAX_K))

    threshold = repo.min_similarity(session)
    vector = (embedder or get_embedder()).embed_query(query)
    rows = repo.nearest_chunks(session, vector, k)

    best = 1.0 - rows[0][1] if rows else None
    hits = [
        SearchHit(
            document_id=chunk.document_id,
            document_name=chunk.document_name,
            article=chunk.article,
            clause=chunk.clause,
            content=chunk.content,
            similarity=1.0 - distance,
        )
        for chunk, distance in rows
        if 1.0 - distance >= threshold
    ]
    if not hits:
        return SearchResult(False, NOT_FOUND_MESSAGE, [], best, threshold)
    return SearchResult(True, None, hits, best, threshold)

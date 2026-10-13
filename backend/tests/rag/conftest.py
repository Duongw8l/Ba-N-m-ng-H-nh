"""Fixture của test RAG: bộ nhúng giả tất định, để không phải tải mô hình thật (~2,3 GB).

Bộ nhúng giả băm từng từ vào một vị trí trong vector 1024 chiều (túi từ) rồi chuẩn hoá. Hai câu
dùng chung nhiều từ thì cosine cao, câu không chung từ nào thì bằng 0. Nó chỉ chứng minh đường ống
và quy tắc (lọc hiệu lực, ngưỡng, transaction), KHÔNG chứng minh chất lượng truy xuất của bge-m3:
chất lượng đo bằng eval/rag_eval.py với mô hình thật.
"""

import math
import re
import zlib
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.rag.embedding import Embedder
from app.rag.models import EMBEDDING_DIM
from app.rag.router import get_embedder_dependency
from app.rag.service import API_MAX_CHUNKS, IngestResult, ingest_document

SAMPLE_TEXT = """Điều 1. Nghỉ học
1. Học sinh nghỉ học phải có đơn xin phép của cha mẹ học sinh.
2. Nghỉ quá hai mươi lăm buổi thì hội đồng xem xét điều kiện lên lớp.
Điều 2. Đồng phục
1. Học sinh mặc đồng phục vào thứ Hai và thứ Sáu hằng tuần.
Điều 3. Điện thoại
Học sinh không dùng điện thoại di động trong giờ học."""

# Câu hỏi dùng nhiều từ của đúng một khoản trong SAMPLE_TEXT.
QUERY_ABSENCE_LETTER = "đơn xin phép nghỉ học của cha mẹ học sinh"
QUERY_UNIFORM = "đồng phục thứ Hai thứ Sáu hằng tuần"
QUERY_OFF_TOPIC = "giá vàng hôm nay tăng bao nhiêu"


class HashingEmbedder:
    """Túi từ băm vào `dim` chiều, đã chuẩn hoá độ dài 1."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in re.findall(r"\w+", text.lower()):
            vector[zlib.crc32(token.encode()) % self.dim] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            vector[0], norm = 1.0, 1.0
        return [value / norm for value in vector]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


@pytest.fixture
def embedder() -> Embedder:
    return HashingEmbedder()


@pytest.fixture
def add_document(db_session: Session, embedder: Embedder) -> Callable[..., IngestResult]:
    """Nạp một văn bản .txt thẳng qua service (không qua HTTP, không ghi nhật ký người dùng)."""

    def add(
        name: str = "Quy chế thử",
        text: str = SAMPLE_TEXT,
        max_chunks: int | None = API_MAX_CHUNKS,
    ) -> IngestResult:
        return ingest_document(
            db_session,
            name=name,
            file_name="quy-che.txt",
            data=text.encode(),
            embedder=embedder,
            user=None,
            max_chunks=max_chunks,
        )

    return add


@pytest.fixture
def rag_client(api_client: TestClient, embedder: Embedder) -> Iterator[TestClient]:
    """`api_client` (DB thật, rollback) thêm bộ nhúng giả. api_client tự xoá override khi xong."""
    app.dependency_overrides[get_embedder_dependency] = lambda: embedder
    yield api_client

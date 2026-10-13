"""Tính vector (embedding) cho đoạn văn bản quy định và câu hỏi (Giai đoạn 7, D-076).

Mặc định bge-m3 (1024 chiều, đa ngôn ngữ, tốt với tiếng Việt), chạy trên CPU (nguyên tắc 8). Mô hình
nạp một lần, lười: lần gọi đầu mất vài chục giây (và tải ~2,3 GB nếu chưa có trong cache
HuggingFace).

`Embedder` là giao diện để test thay bằng bộ nhúng giả (tests/rag/conftest.py) mà không cần tải mô
hình. Mã gọi nhận `Embedder` qua tham số hoặc `get_embedder()`; router dùng dependency để test
ghi đè.
"""

import threading
from functools import lru_cache
from typing import Any, Protocol

from app.core.config import get_settings

# Đoạn dài nhất khoảng 2000 ký tự (~600 token); 1024 token là dư, và chặn tốn bộ nhớ nếu có đoạn lạ.
MAX_SEQUENCE_TOKENS = 1024
BATCH_SIZE = 16


class EmbeddingUnavailable(RuntimeError):
    """Không nạp được mô hình (thiếu thư viện, không tải được, sai số chiều). Router trả 503."""


class Embedder(Protocol):
    dim: int

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        """Vector (đã chuẩn hoá độ dài 1) của các đoạn văn bản quy định, cùng thứ tự đầu vào."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Vector (đã chuẩn hoá độ dài 1) của một câu hỏi."""
        ...


class SentenceTransformerEmbedder:
    """Mô hình sentence-transformers chạy trên CPU. Nạp lười, an toàn khi nhiều luồng cùng gọi."""

    def __init__(self, model_name: str, dim: int) -> None:
        self.model_name = model_name
        self.dim = dim
        # Họ e5 yêu cầu tiền tố; bge-m3 thì không.
        needs_prefix = "e5" in model_name.lower()
        self._query_prefix = "query: " if needs_prefix else ""
        self._passage_prefix = "passage: " if needs_prefix else ""
        self._model: Any = None
        self._lock = threading.Lock()

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(self.model_name, device="cpu")
        except Exception as error:  # thiếu thư viện, không có mạng để tải, tệp mô hình hỏng...
            raise EmbeddingUnavailable(
                f"Không nạp được mô hình embedding '{self.model_name}'. Chạy make rag-model để "
                f"tải trước (cần mạng lần đầu). Chi tiết: {error}"
            ) from error
        actual = model.get_embedding_dimension()
        if actual != self.dim:
            raise EmbeddingUnavailable(
                f"Mô hình '{self.model_name}' cho vector {actual} chiều nhưng cấu hình "
                f"EMBEDDING_DIM là {self.dim}. Đổi mô hình cần migration đổi cột vector."
            )
        model.max_seq_length = min(model.max_seq_length or MAX_SEQUENCE_TOKENS, MAX_SEQUENCE_TOKENS)
        self._model = model
        return model

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        with self._lock:  # nạp mô hình và suy luận tuần tự: CPU là điểm nghẽn, đỡ tranh chấp bộ nhớ
            model = self._load()
            vectors = model.encode(
                texts,
                batch_size=BATCH_SIZE,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        return [[float(value) for value in vector] for vector in vectors]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return self._encode([f"{self._passage_prefix}{text}" for text in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._encode([f"{self._query_prefix}{text}"])[0]


@lru_cache
def get_embedder() -> Embedder:
    """Bộ nhúng dùng chung của tiến trình, theo EMBEDDING_MODEL và EMBEDDING_DIM."""
    settings = get_settings()
    return SentenceTransformerEmbedder(settings.embedding_model, settings.embedding_dim)

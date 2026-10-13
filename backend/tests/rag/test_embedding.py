"""SentenceTransformerEmbedder với mô hình giả (nhanh, không tải gì) và, khi RUN_EMBEDDING_TESTS=1,
với bge-m3 thật (cần ~2,3 GB tải về lần đầu và vài chục giây nạp)."""

import os
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from app.rag.embedding import EmbeddingUnavailable, SentenceTransformerEmbedder, get_embedder


class FakeModel:
    """Giống SentenceTransformer ở những gì embedder dùng; ghi lại mọi lần gọi."""

    instances: list["FakeModel"] = []

    def __init__(self, name: str, device: str | None = None, dim: int = 8) -> None:
        self.name, self.device, self.dim = name, device, dim
        self.max_seq_length = 8192
        self.encoded: list[list[str]] = []
        FakeModel.instances.append(self)

    def get_embedding_dimension(self) -> int:
        return self.dim

    def encode(self, texts: list[str], **options: object) -> np.ndarray:
        self.encoded.append(list(texts))
        self.options = options
        return np.ones((len(texts), self.dim), dtype=np.float32) / np.sqrt(self.dim)


@pytest.fixture
def fake_library(monkeypatch: pytest.MonkeyPatch) -> type[FakeModel]:
    FakeModel.instances = []
    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=FakeModel)
    )
    return FakeModel


def test_model_is_loaded_lazily_once_on_cpu_with_bounded_sequence_length(
    fake_library: type[FakeModel],
) -> None:
    embedder = SentenceTransformerEmbedder("BAAI/bge-m3", dim=8)
    assert fake_library.instances == []  # chưa nạp khi mới tạo

    embedder.embed_query("câu hỏi")
    embedder.embed_passages(["a", "b"])

    [model] = fake_library.instances
    assert (model.name, model.device) == ("BAAI/bge-m3", "cpu")
    assert model.max_seq_length == 1024
    assert model.options["normalize_embeddings"] is True


def test_bge_gets_no_prefix_but_e5_gets_query_and_passage_prefixes(
    fake_library: type[FakeModel],
) -> None:
    bge = SentenceTransformerEmbedder("BAAI/bge-m3", dim=8)
    bge.embed_query("hỏi gì")
    bge.embed_passages(["đoạn một"])
    e5 = SentenceTransformerEmbedder("intfloat/multilingual-e5-large", dim=8)
    e5.embed_query("hỏi gì")
    e5.embed_passages(["đoạn một"])

    bge_model, e5_model = fake_library.instances
    assert bge_model.encoded == [["hỏi gì"], ["đoạn một"]]
    assert e5_model.encoded == [["query: hỏi gì"], ["passage: đoạn một"]]


def test_vectors_are_plain_float_lists_in_input_order(fake_library: type[FakeModel]) -> None:
    embedder = SentenceTransformerEmbedder("BAAI/bge-m3", dim=8)

    vectors = embedder.embed_passages(["a", "b", "c"])

    assert len(vectors) == 3
    assert all(type(v) is list and len(v) == 8 and type(v[0]) is float for v in vectors)


def test_empty_input_does_not_load_the_model(fake_library: type[FakeModel]) -> None:
    embedder = SentenceTransformerEmbedder("BAAI/bge-m3", dim=8)

    assert embedder.embed_passages([]) == []
    assert fake_library.instances == []


def test_dimension_mismatch_is_reported_with_the_configuration_name(
    fake_library: type[FakeModel],
) -> None:
    embedder = SentenceTransformerEmbedder("BAAI/bge-m3", dim=1024)  # mô hình giả có 8 chiều

    with pytest.raises(EmbeddingUnavailable, match="EMBEDDING_DIM"):
        embedder.embed_query("câu hỏi")


def test_load_failure_becomes_embedding_unavailable_with_a_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Failing:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise OSError("không có mạng")

    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Failing)
    )
    embedder = SentenceTransformerEmbedder("BAAI/bge-m3", dim=8)

    with pytest.raises(EmbeddingUnavailable, match="make rag-model"):
        embedder.embed_query("câu hỏi")


def test_default_embedder_follows_the_configuration() -> None:
    get_embedder.cache_clear()
    try:
        embedder = get_embedder()
        assert isinstance(embedder, SentenceTransformerEmbedder)
        assert (embedder.model_name, embedder.dim) == ("BAAI/bge-m3", 1024)
    finally:
        get_embedder.cache_clear()


@pytest.mark.skipif(
    os.environ.get("RUN_EMBEDDING_TESTS") != "1",
    reason="cần mô hình thật: đặt RUN_EMBEDDING_TESTS=1 (tải ~2,3 GB lần đầu)",
)
def test_real_bge_m3_gives_unit_vectors_and_ranks_the_relevant_passage_first() -> None:
    embedder = SentenceTransformerEmbedder("BAAI/bge-m3", dim=1024)
    passages = [
        "Học sinh nghỉ học phải có đơn xin phép của cha mẹ học sinh.",
        "Học sinh mặc đồng phục vào thứ Hai và thứ Sáu hằng tuần.",
        "Điểm kiểm tra tuần được làm tròn đến 0,5 điểm.",
    ]

    vectors = np.array(embedder.embed_passages(passages))
    query = np.array(embedder.embed_query("Nghỉ học có cần đơn không?"))

    assert vectors.shape == (3, 1024)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-4)
    assert int(np.argmax(vectors @ query)) == 0

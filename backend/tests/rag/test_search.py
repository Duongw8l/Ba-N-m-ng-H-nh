from collections.abc import Callable

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.enums import RegulationStatus, UserRole
from app.core.models import Setting
from app.rag import repository as repo
from app.rag.embedding import Embedder
from app.rag.models import RegulationChunk, RegulationDocument
from app.rag.parsing import DocumentError
from app.rag.repository import MissingSimilaritySetting
from app.rag.search import MAX_K, NOT_FOUND_MESSAGE, search_regulation
from app.rag.service import (
    DocumentNotFound,
    DuplicateDocument,
    IngestResult,
    change_status,
    ingest_document,
)
from tests.rag.conftest import (
    QUERY_ABSENCE_LETTER,
    QUERY_OFF_TOPIC,
    QUERY_UNIFORM,
    SAMPLE_TEXT,
)

pytestmark = pytest.mark.db

AddDocument = Callable[..., IngestResult]


def set_threshold(session: Session, value: float) -> None:
    session.execute(update(Setting).where(Setting.key == "rag_min_similarity").values(value=value))
    session.flush()


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def admin(session: Session) -> User:
    user = session.scalar(select(User).where(User.role == UserRole.ADMIN))
    assert user is not None
    return user


# --- Nạp ----------------------------------------------------------------------------------------


def test_ingest_stores_document_and_chunks_with_metadata_and_vectors(
    db_session: Session, add_document: AddDocument
) -> None:
    result = add_document()

    assert (result.article_count, result.chunk_count) == (3, 4)
    assert result.document.name == "Quy chế thử"
    assert result.document.status is RegulationStatus.ACTIVE
    chunks = db_session.scalars(
        select(RegulationChunk)
        .where(RegulationChunk.document_id == result.document.id)
        .order_by(RegulationChunk.id)
    ).all()
    assert [(c.article, c.clause) for c in chunks] == [
        ("Điều 1", "Khoản 1"),
        ("Điều 1", "Khoản 2"),
        ("Điều 2", "Khoản 1"),
        ("Điều 3", None),
    ]
    assert all(c.document_name == "Quy chế thử" for c in chunks)
    assert all(c.embedding is not None and len(c.embedding) == 1024 for c in chunks)
    assert chunks[0].content.startswith("Điều 1. Nghỉ học\n1. Học sinh nghỉ học phải có đơn")


def test_a_second_active_document_with_the_same_name_is_refused(
    db_session: Session, add_document: AddDocument
) -> None:
    add_document()

    with pytest.raises(DuplicateDocument):
        add_document()

    assert count(db_session, RegulationDocument) == 1


def test_same_name_can_be_loaded_again_after_the_old_one_expired(
    db_session: Session, add_document: AddDocument
) -> None:
    first = add_document()
    change_status(db_session, admin(db_session), first.document.id, RegulationStatus.EXPIRED)

    second = add_document()

    assert second.document.id != first.document.id
    assert count(db_session, RegulationDocument) == 2


def test_ingest_failure_while_saving_chunks_leaves_no_document_behind(
    db_session: Session, embedder: Embedder, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("đĩa đầy giữa chừng")

    monkeypatch.setattr(repo, "add_chunks", explode)

    with pytest.raises(RuntimeError, match="đĩa đầy"):
        ingest_document(
            db_session,
            name="Hỏng giữa chừng",
            file_name="a.txt",
            data=SAMPLE_TEXT.encode(),
            embedder=embedder,
            user=None,
        )

    assert count(db_session, RegulationDocument) == 0
    assert count(db_session, RegulationChunk) == 0


def test_embedder_returning_wrong_number_of_vectors_writes_nothing(
    db_session: Session, embedder: Embedder
) -> None:
    class Broken:
        dim = embedder.dim

        def embed_passages(self, texts: list[str]) -> list[list[float]]:
            return embedder.embed_passages(texts)[:-1]

        def embed_query(self, text: str) -> list[float]:
            return embedder.embed_query(text)

    with pytest.raises(RuntimeError, match="không khớp"):
        ingest_document(
            db_session,
            name="Thiếu vector",
            file_name="a.txt",
            data=SAMPLE_TEXT.encode(),
            embedder=Broken(),
            user=None,
        )

    assert count(db_session, RegulationDocument) == 0


def test_document_with_too_many_chunks_is_refused_unless_unlimited(
    db_session: Session, add_document: AddDocument
) -> None:
    with pytest.raises(DocumentError, match="quá 3"):
        add_document(max_chunks=3)  # SAMPLE_TEXT có 4 đoạn
    assert count(db_session, RegulationDocument) == 0

    assert add_document(max_chunks=None).chunk_count == 4


@pytest.mark.parametrize("name", ["", "   ", "x" * 201])
def test_blank_or_overlong_name_is_refused(add_document: AddDocument, name: str) -> None:
    with pytest.raises(DocumentError):
        add_document(name=name)


def test_text_without_any_chunk_is_refused(add_document: AddDocument) -> None:
    # Chỉ có chương và nơi nhận: hợp lệ về chữ nhưng không có đoạn nào để lưu.
    text = "Chương I\nQUY ĐỊNH CHUNG\nNơi nhận:\n- Lưu: VT, văn phòng nhà trường."

    with pytest.raises(DocumentError, match="Không tách được đoạn nào"):
        add_document(text=text)


# --- Tìm ----------------------------------------------------------------------------------------


def test_search_returns_the_best_clause_first_with_citation_fields(
    db_session: Session, embedder: Embedder, add_document: AddDocument
) -> None:
    result = add_document()

    found = search_regulation(db_session, QUERY_ABSENCE_LETTER, embedder=embedder)

    assert found.found is True
    assert found.message is None
    top = found.hits[0]
    assert (top.document_id, top.document_name) == (result.document.id, "Quy chế thử")
    assert (top.article, top.clause) == ("Điều 1", "Khoản 1")
    assert "đơn xin phép" in top.content
    similarities = [hit.similarity for hit in found.hits]
    assert similarities == sorted(similarities, reverse=True)
    assert found.best_similarity == pytest.approx(top.similarity)


def test_search_finds_a_different_clause_for_a_different_question(
    db_session: Session, embedder: Embedder, add_document: AddDocument
) -> None:
    add_document()

    top = search_regulation(db_session, QUERY_UNIFORM, embedder=embedder).hits[0]

    assert (top.article, top.clause) == ("Điều 2", "Khoản 1")


def test_k_limits_the_number_of_hits_and_is_clamped(
    db_session: Session, embedder: Embedder, add_document: AddDocument
) -> None:
    add_document()
    set_threshold(db_session, 0.0)  # mọi đoạn đều qua ngưỡng

    assert len(search_regulation(db_session, "học sinh", 2, embedder=embedder).hits) == 2
    assert len(search_regulation(db_session, "học sinh", 0, embedder=embedder).hits) == 1
    assert len(search_regulation(db_session, "học sinh", 100, embedder=embedder).hits) == 4
    assert MAX_K >= 4


def test_off_topic_question_is_not_found_and_returns_no_passage_at_all(
    db_session: Session, embedder: Embedder, add_document: AddDocument
) -> None:
    add_document()

    result = search_regulation(db_session, QUERY_OFF_TOPIC, embedder=embedder)

    assert result.found is False
    assert result.message == NOT_FOUND_MESSAGE
    assert result.hits == []
    assert result.best_similarity is not None
    assert result.best_similarity < result.min_similarity


def test_search_with_no_documents_is_not_found(db_session: Session, embedder: Embedder) -> None:
    result = search_regulation(db_session, QUERY_ABSENCE_LETTER, embedder=embedder)

    assert (result.found, result.hits, result.best_similarity) == (False, [], None)
    assert result.message == NOT_FOUND_MESSAGE


def test_threshold_comes_from_settings_and_changes_the_outcome(
    db_session: Session, embedder: Embedder, add_document: AddDocument
) -> None:
    add_document()

    set_threshold(db_session, 0.99)
    assert search_regulation(db_session, QUERY_ABSENCE_LETTER, embedder=embedder).found is False

    set_threshold(db_session, 0.0)
    assert search_regulation(db_session, QUERY_OFF_TOPIC, embedder=embedder).found is True


def test_a_passage_exactly_at_the_threshold_is_accepted_but_not_below_it(
    db_session: Session, embedder: Embedder, add_document: AddDocument
) -> None:
    add_document()
    set_threshold(db_session, 0.0)
    best = search_regulation(db_session, QUERY_ABSENCE_LETTER, 1, embedder=embedder).hits[0]

    set_threshold(db_session, best.similarity)
    at_threshold = search_regulation(db_session, QUERY_ABSENCE_LETTER, 1, embedder=embedder)
    set_threshold(db_session, best.similarity + 1e-6)
    above = search_regulation(db_session, QUERY_ABSENCE_LETTER, 1, embedder=embedder)

    assert at_threshold.found is True
    assert above.found is False
    assert above.hits == []


def test_missing_threshold_setting_is_reported(db_session: Session, embedder: Embedder) -> None:
    db_session.execute(Setting.__table__.delete().where(Setting.key == "rag_min_similarity"))

    with pytest.raises(MissingSimilaritySetting, match="make migrate"):
        search_regulation(db_session, QUERY_ABSENCE_LETTER, embedder=embedder)


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_blank_query_is_refused(db_session: Session, embedder: Embedder, query: str) -> None:
    with pytest.raises(ValueError):
        search_regulation(db_session, query, embedder=embedder)


# --- Hiệu lực -----------------------------------------------------------------------------------


def test_expired_document_never_appears_and_reactivating_brings_it_back(
    db_session: Session, embedder: Embedder, add_document: AddDocument
) -> None:
    document = add_document().document
    user = admin(db_session)

    change_status(db_session, user, document.id, RegulationStatus.EXPIRED)
    expired = search_regulation(db_session, QUERY_ABSENCE_LETTER, 10, embedder=embedder)
    change_status(db_session, user, document.id, RegulationStatus.ACTIVE)
    active = search_regulation(db_session, QUERY_ABSENCE_LETTER, 10, embedder=embedder)

    assert (expired.found, expired.hits, expired.best_similarity) == (False, [], None)
    assert active.found is True
    assert {hit.document_id for hit in active.hits} == {document.id}


def test_only_the_active_copy_is_returned_when_an_old_version_is_expired(
    db_session: Session, embedder: Embedder, add_document: AddDocument
) -> None:
    old = add_document(name="Quy chế bản cũ").document
    new = add_document(name="Quy chế bản mới").document
    set_threshold(db_session, 0.0)

    before = {
        h.document_id for h in search_regulation(db_session, "nghỉ học", 10, embedder=embedder).hits
    }
    change_status(db_session, admin(db_session), old.id, RegulationStatus.EXPIRED)
    after = {
        h.document_id for h in search_regulation(db_session, "nghỉ học", 10, embedder=embedder).hits
    }

    assert before == {old.id, new.id}
    assert after == {new.id}


def test_expiring_sets_the_time_and_reactivating_clears_it(
    db_session: Session, add_document: AddDocument
) -> None:
    document = add_document().document
    user = admin(db_session)

    expired = change_status(db_session, user, document.id, RegulationStatus.EXPIRED)
    assert expired.document.status is RegulationStatus.EXPIRED
    assert expired.document.expired_at is not None

    again = change_status(db_session, user, document.id, RegulationStatus.ACTIVE)
    assert again.document.status is RegulationStatus.ACTIVE
    assert again.document.expired_at is None


def test_reactivating_is_refused_while_another_copy_with_the_same_name_is_active(
    db_session: Session, add_document: AddDocument
) -> None:
    first = add_document().document
    user = admin(db_session)
    change_status(db_session, user, first.id, RegulationStatus.EXPIRED)
    add_document()

    with pytest.raises(DuplicateDocument):
        change_status(db_session, user, first.id, RegulationStatus.ACTIVE)

    assert db_session.get(RegulationDocument, first.id).status is RegulationStatus.EXPIRED  # type: ignore[union-attr]


def test_changing_status_of_an_unknown_document_is_reported(db_session: Session) -> None:
    with pytest.raises(DocumentNotFound):
        change_status(db_session, admin(db_session), 999_999, RegulationStatus.EXPIRED)


def test_document_list_counts_articles_and_chunks_and_puts_active_first(
    db_session: Session, add_document: AddDocument
) -> None:
    old = add_document(name="Bản cũ").document
    add_document(name="Bản mới")
    change_status(db_session, admin(db_session), old.id, RegulationStatus.EXPIRED)

    rows = repo.list_documents(db_session)

    assert [(r.document.name, r.article_count, r.chunk_count) for r in rows] == [
        ("Bản mới", 3, 4),
        ("Bản cũ", 3, 4),
    ]

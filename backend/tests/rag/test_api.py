from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.models import AuditLog
from app.core.enums import AuditAction
from app.core.models import Setting
from app.main import app
from app.rag import parsing
from app.rag.embedding import EmbeddingUnavailable
from app.rag.models import RegulationChunk, RegulationDocument
from app.rag.router import get_embedder_dependency
from tests.rag.conftest import (
    QUERY_ABSENCE_LETTER,
    QUERY_OFF_TOPIC,
    QUERY_UNIFORM,
    SAMPLE_TEXT,
)

pytestmark = pytest.mark.db

API = "/api/v1"
ADMIN = "admin@example.com"
# Mọi vai trò khác Admin: BGH, GVCN, GVBM thuần, và GVBM kiêm GVCN.
NON_ADMINS = [
    "bgh1@example.com",
    "gvcn.11a2@example.com",
    "gv.van.11@example.com",
    "gv.toan.11@example.com",
]
Headers = Callable[[str], dict[str, str]]


def upload(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Quy chế thử",
    file_name: str = "quy-che.txt",
    data: bytes = SAMPLE_TEXT.encode(),
) -> Response:
    return client.post(
        f"{API}/admin/regulations",
        headers=headers,
        data={"name": name},
        files={"file": (file_name, data, "application/octet-stream")},
    )


def expire(client: TestClient, headers: dict[str, str], document_id: int) -> Response:
    return client.patch(
        f"{API}/admin/regulations/{document_id}", headers=headers, json={"status": "expired"}
    )


def document_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(RegulationDocument)) or 0


def audit_rows(session: Session, action: AuditAction) -> list[AuditLog]:
    return list(session.scalars(select(AuditLog).where(AuditLog.action == action)))


# --- Phân quyền: 4 vai trò × 3 endpoint quản trị + chưa đăng nhập --------------------------------


def test_admin_can_use_all_three_admin_endpoints(
    rag_client: TestClient, auth_headers: Headers
) -> None:
    headers = auth_headers(ADMIN)

    created = upload(rag_client, headers)
    listed = rag_client.get(f"{API}/admin/regulations", headers=headers)
    patched = rag_client.patch(
        f"{API}/admin/regulations/{created.json()['id']}",
        headers=headers,
        json={"status": "expired"},
    )

    assert (created.status_code, listed.status_code, patched.status_code) == (201, 200, 200)


@pytest.mark.parametrize("email", NON_ADMINS)
def test_every_other_role_gets_403_on_all_admin_endpoints_and_nothing_is_written(
    rag_client: TestClient, auth_headers: Headers, db_session: Session, email: str
) -> None:
    other = auth_headers(email)
    document_id = upload(rag_client, auth_headers(ADMIN)).json()["id"]

    responses = [
        rag_client.get(f"{API}/admin/regulations", headers=other),
        upload(rag_client, other, name="Bản lạ"),
        rag_client.patch(
            f"{API}/admin/regulations/{document_id}", headers=other, json={"status": "expired"}
        ),
    ]

    assert [r.status_code for r in responses] == [403, 403, 403]
    assert document_count(db_session) == 1  # chỉ bản của Admin
    status_now = db_session.scalar(select(RegulationDocument.status))
    assert status_now.value == "active"  # type: ignore[union-attr]  # PATCH bị từ chối không đổi gì
    assert audit_rows(db_session, AuditAction.UPDATE_REGULATION) == []


@pytest.mark.parametrize("email", NON_ADMINS)
def test_non_admin_gets_403_even_for_a_malformed_upload(
    rag_client: TestClient, auth_headers: Headers, email: str
) -> None:
    # Thiếu tệp và tên: người không có quyền thấy 403, không thấy 422 (không lộ hình dạng yêu cầu).
    response = rag_client.post(f"{API}/admin/regulations", headers=auth_headers(email))

    assert response.status_code == 403


def test_without_a_token_every_endpoint_is_401(rag_client: TestClient) -> None:
    responses = [
        rag_client.get(f"{API}/admin/regulations"),
        rag_client.post(f"{API}/admin/regulations"),
        rag_client.patch(f"{API}/admin/regulations/1", json={"status": "expired"}),
        rag_client.get(f"{API}/regulations/search", params={"q": "nghỉ học"}),
    ]

    assert [r.status_code for r in responses] == [401, 401, 401, 401]


# --- Tải lên ------------------------------------------------------------------------------------


def test_upload_returns_summary_stores_chunks_and_writes_an_audit_row(
    rag_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    response = upload(rag_client, auth_headers(ADMIN), name="  Quy chế   thử  ")

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Quy chế thử"  # khoảng trắng thừa được gộp
    assert (body["status"], body["status_label"]) == ("active", "Còn hiệu lực")
    assert (body["article_count"], body["chunk_count"]) == (3, 4)
    assert body["file_name"] == "quy-che.txt"
    assert body["expired_at"] is None
    chunks = db_session.scalar(select(func.count()).select_from(RegulationChunk))
    assert chunks == 4
    [row] = audit_rows(db_session, AuditAction.UPLOAD_REGULATION)
    assert row.class_id is None
    assert row.details == {
        "document_id": body["id"],
        "name": "Quy chế thử",
        "file_name": "quy-che.txt",
        "chunk_count": 4,
    }


def test_upload_keeps_only_the_file_name_and_never_a_path(
    rag_client: TestClient, auth_headers: Headers
) -> None:
    response = upload(rag_client, auth_headers(ADMIN), file_name="../../etc/quy-che.txt")

    assert response.json()["file_name"] == "quy-che.txt"


@pytest.mark.parametrize(
    ("file_name", "data", "expected"),
    [
        ("bang-diem.xlsx", b"x" * 50, "Chỉ nhận tệp"),
        ("quy-che", b"x" * 50, "Chỉ nhận tệp"),
        ("trong.txt", b"", "Tệp rỗng"),
        ("khoang-trang.txt", b"   \n  \n", "không có nội dung"),
        ("hong.pdf", b"%PDF-1.4 hong het roi" * 5, "PDF"),
        ("khong-phai-docx.docx", b"PK\x03\x04" + b"x" * 40, "DOCX"),
    ],
)
def test_unusable_file_is_422_with_a_clear_message_and_writes_nothing(
    rag_client: TestClient,
    auth_headers: Headers,
    db_session: Session,
    file_name: str,
    data: bytes,
    expected: str,
) -> None:
    response = upload(rag_client, auth_headers(ADMIN), file_name=file_name, data=data)

    assert response.status_code == 422
    assert expected in response.json()["detail"]
    assert document_count(db_session) == 0
    assert audit_rows(db_session, AuditAction.UPLOAD_REGULATION) == []


def test_upload_without_name_or_file_is_422_for_admin(
    rag_client: TestClient, auth_headers: Headers
) -> None:
    headers = auth_headers(ADMIN)

    no_file = rag_client.post(f"{API}/admin/regulations", headers=headers, data={"name": "A"})
    no_name = rag_client.post(
        f"{API}/admin/regulations", headers=headers, files={"file": ("a.txt", b"x" * 50)}
    )
    blank_name = upload(rag_client, headers, name="")

    assert (no_file.status_code, no_name.status_code, blank_name.status_code) == (422, 422, 422)


def test_file_over_the_size_limit_is_413(
    rag_client: TestClient,
    auth_headers: Headers,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(parsing, "MAX_FILE_BYTES", 100)
    monkeypatch.setattr("app.rag.router.MAX_FILE_BYTES", 100)

    response = upload(rag_client, auth_headers(ADMIN), data=b"Dieu 1. " + b"a" * 200)

    assert response.status_code == 413
    assert document_count(db_session) == 0


def test_uploading_a_name_that_is_still_active_is_409_until_the_old_one_expires(
    rag_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    first = upload(rag_client, headers)

    duplicate = upload(rag_client, headers)
    rag_client.patch(
        f"{API}/admin/regulations/{first.json()['id']}", headers=headers, json={"status": "expired"}
    )
    replacement = upload(rag_client, headers)

    assert (first.status_code, duplicate.status_code, replacement.status_code) == (201, 409, 201)
    assert "hết hiệu lực" in duplicate.json()["detail"]
    assert document_count(db_session) == 2


def test_missing_embedding_model_is_503_and_writes_nothing(
    rag_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    class Unavailable:
        dim = 1024

        def embed_passages(self, texts: list[str]) -> list[list[float]]:
            raise EmbeddingUnavailable("Không nạp được mô hình embedding 'x'.")

        def embed_query(self, text: str) -> list[float]:
            raise EmbeddingUnavailable("Không nạp được mô hình embedding 'x'.")

    app.dependency_overrides[get_embedder_dependency] = Unavailable

    response = upload(rag_client, auth_headers(ADMIN))
    search = rag_client.get(
        f"{API}/regulations/search", params={"q": "nghỉ học"}, headers=auth_headers(ADMIN)
    )

    assert (response.status_code, search.status_code) == (503, 503)
    assert "mô hình embedding" in response.json()["detail"]
    assert document_count(db_session) == 0


# --- Danh sách và đổi hiệu lực -------------------------------------------------------------------


def test_list_shows_status_label_and_counts(rag_client: TestClient, auth_headers: Headers) -> None:
    headers = auth_headers(ADMIN)
    upload(rag_client, headers, name="Bản cũ")
    new_id = upload(rag_client, headers, name="Bản mới").json()["id"]
    expire(rag_client, headers, new_id)

    body = rag_client.get(f"{API}/admin/regulations", headers=headers).json()

    assert [(d["name"], d["status"], d["status_label"]) for d in body] == [
        ("Bản cũ", "active", "Còn hiệu lực"),
        ("Bản mới", "expired", "Hết hiệu lực"),
    ]
    assert all((d["article_count"], d["chunk_count"]) == (3, 4) for d in body)
    assert body[1]["expired_at"] is not None


def test_status_change_is_audited_only_when_it_actually_changes(
    rag_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    document_id = upload(rag_client, headers).json()["id"]
    url = f"{API}/admin/regulations/{document_id}"

    expired = rag_client.patch(url, headers=headers, json={"status": "expired"})
    expired_again = rag_client.patch(url, headers=headers, json={"status": "expired"})
    reactivated = rag_client.patch(url, headers=headers, json={"status": "active"})

    assert [r.json()["status"] for r in (expired, expired_again, reactivated)] == [
        "expired",
        "expired",
        "active",
    ]
    rows = audit_rows(db_session, AuditAction.UPDATE_REGULATION)
    assert [(r.details["from"], r.details["to"]) for r in rows] == [
        ("active", "expired"),
        ("expired", "active"),
    ]
    assert all(r.details["document_id"] == document_id for r in rows)


def test_patch_with_unknown_id_or_bad_status_is_rejected(
    rag_client: TestClient, auth_headers: Headers
) -> None:
    headers = auth_headers(ADMIN)
    document_id = upload(rag_client, headers).json()["id"]

    unknown = rag_client.patch(
        f"{API}/admin/regulations/999999", headers=headers, json={"status": "expired"}
    )
    bad = rag_client.patch(
        f"{API}/admin/regulations/{document_id}", headers=headers, json={"status": "deleted"}
    )

    assert (unknown.status_code, bad.status_code) == (404, 422)


def test_reactivating_while_a_newer_copy_is_active_is_409(
    rag_client: TestClient, auth_headers: Headers
) -> None:
    headers = auth_headers(ADMIN)
    old_id = upload(rag_client, headers).json()["id"]
    expire(rag_client, headers, old_id)
    upload(rag_client, headers)

    response = rag_client.patch(
        f"{API}/admin/regulations/{old_id}", headers=headers, json={"status": "active"}
    )

    assert response.status_code == 409


# --- Tìm ----------------------------------------------------------------------------------------


def search(client: TestClient, headers: dict[str, str], q: str, **params: object) -> Response:
    return client.get(f"{API}/regulations/search", params={"q": q, **params}, headers=headers)


@pytest.mark.parametrize("email", [ADMIN, *NON_ADMINS])
def test_every_logged_in_role_can_search(
    rag_client: TestClient, auth_headers: Headers, email: str
) -> None:
    upload(rag_client, auth_headers(ADMIN))

    response = search(rag_client, auth_headers(email), QUERY_ABSENCE_LETTER)

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["message"] is None
    top = body["hits"][0]
    assert (top["document_name"], top["article"], top["clause"]) == (
        "Quy chế thử",
        "Điều 1",
        "Khoản 1",
    )
    assert body["min_similarity"] <= top["similarity"] <= 1
    assert body["best_similarity"] == top["similarity"]
    assert body["min_similarity"] == 0.56  # giá trị mặc định của migration (đo bằng bge-m3, D-082)


def test_search_picks_the_clause_that_matches_the_question(
    rag_client: TestClient, auth_headers: Headers
) -> None:
    headers = auth_headers("bgh1@example.com")
    upload(rag_client, auth_headers(ADMIN))

    top = search(rag_client, headers, QUERY_UNIFORM).json()["hits"][0]

    assert (top["article"], top["clause"]) == ("Điều 2", "Khoản 1")
    assert "đồng phục" in top["content"]


def test_off_topic_question_returns_the_not_found_message_and_no_passage(
    rag_client: TestClient, auth_headers: Headers
) -> None:
    upload(rag_client, auth_headers(ADMIN))

    body = search(rag_client, auth_headers("gv.van.11@example.com"), QUERY_OFF_TOPIC).json()

    assert body["found"] is False
    assert body["message"] == "Không tìm thấy trong văn bản quy định"
    assert body["hits"] == []


def test_expired_document_disappears_from_search_through_the_api_and_comes_back(
    rag_client: TestClient, auth_headers: Headers
) -> None:
    admin = auth_headers(ADMIN)
    teacher = auth_headers("gvcn.11a2@example.com")
    document_id = upload(rag_client, admin).json()["id"]
    url = f"{API}/admin/regulations/{document_id}"

    rag_client.patch(url, headers=admin, json={"status": "expired"})
    while_expired = search(rag_client, teacher, QUERY_ABSENCE_LETTER).json()
    rag_client.patch(url, headers=admin, json={"status": "active"})
    after = search(rag_client, teacher, QUERY_ABSENCE_LETTER).json()

    assert (while_expired["found"], while_expired["hits"]) == (False, [])
    assert after["found"] is True


@pytest.mark.parametrize(
    "params",
    [
        {"q": ""},
        {"q": "x" * 501},
        {"q": "nghỉ học", "k": 0},
        {"q": "nghỉ học", "k": 11},
        {"q": "nghỉ học", "k": "nhieu"},
        {},
    ],
)
def test_search_validates_its_parameters(
    rag_client: TestClient, auth_headers: Headers, params: dict[str, object]
) -> None:
    response = rag_client.get(
        f"{API}/regulations/search", params=params, headers=auth_headers(ADMIN)
    )

    assert response.status_code == 422


def test_blank_question_is_422(rag_client: TestClient, auth_headers: Headers) -> None:
    assert search(rag_client, auth_headers(ADMIN), "   ").status_code == 422


def test_k_limits_the_number_of_hits(
    rag_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    upload(rag_client, auth_headers(ADMIN))
    # Hạ ngưỡng về 0 để cả 4 đoạn đều qua; câu hỏi chung dùng từ có ở nhiều đoạn.
    db_session.execute(update(Setting).where(Setting.key == "rag_min_similarity").values(value=0.0))

    two = search(rag_client, auth_headers(ADMIN), "học sinh", k=2).json()
    default = search(rag_client, auth_headers(ADMIN), "học sinh").json()

    assert len(two["hits"]) == 2
    assert len(default["hits"]) == 4  # k mặc định là 4

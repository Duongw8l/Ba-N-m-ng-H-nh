"""API trợ lý AI (D-091): phân quyền cả 4 vai trò, mã lỗi, giới hạn, đánh giá đúng/sai."""

from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assistant.llm import LLMError, LLMNotConfigured, LLMProvider
from app.assistant.models import AiLog
from app.assistant.router import get_provider_factory
from app.core.enums import AssistantFeedback
from app.main import app
from app.rag.embedding import Embedder
from app.rag.router import get_embedder_dependency
from tests.assistant.conftest import ScriptedLLM, call, says, wants

pytestmark = pytest.mark.db

GVCN_11A2 = "gvcn.11a2@example.com"
GVBM_VAN_11 = "gv.van.11@example.com"
PRINCIPAL = "bgh1@example.com"
ADMIN = "admin@example.com"

CHAT = "/api/v1/assistant/chat"
Headers = Callable[[str], dict[str, str]]


@pytest.fixture
def use_llm(api_client: TestClient, embedder: Embedder) -> Iterator[Callable[..., None]]:
    """Cài LLM giả (hoặc lỗi cấu hình) cho `/assistant/chat`; api_client tự xoá override."""
    app.dependency_overrides[get_embedder_dependency] = lambda: embedder

    def install(llm: LLMProvider | None = None, *, error: Exception | None = None) -> None:
        def factory() -> LLMProvider:
            if error is not None:
                raise error
            assert llm is not None
            return llm

        app.dependency_overrides[get_provider_factory] = lambda: factory

    yield install


def ask(
    client: TestClient, headers: dict[str, str], question: str = "Xin chào.", **extra: Any
) -> Any:
    return client.post(CHAT, json={"question": question, **extra}, headers=headers)


# --- Phân quyền theo vai trò ------------------------------------------------------------------


def test_chat_requires_login(api_client: TestClient, use_llm: Callable[..., None]) -> None:
    use_llm(ScriptedLLM([]))

    assert api_client.post(CHAT, json={"question": "Xin chào."}).status_code == 401
    bad = {"Authorization": "Bearer khong.hop.le"}
    assert api_client.post(CHAT, json={"question": "Xin chào."}, headers=bad).status_code == 401


@pytest.mark.parametrize(
    ("email", "status_code"),
    [(GVCN_11A2, 200), (GVBM_VAN_11, 200), (PRINCIPAL, 200), (ADMIN, 403)],
)
def test_chat_role_matrix(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: Callable[..., None],
    email: str,
    status_code: int,
) -> None:
    llm = ScriptedLLM([says("Chào bạn.")])
    use_llm(llm)

    response = ask(api_client, auth_headers(email))

    assert response.status_code == status_code
    if status_code == 200:
        body = response.json()
        assert body["answer"] == "Chào bạn." and body["sources"] == []
        assert set(body) == {
            "log_id",
            "answer",
            "sources",
            "blocked",
            "ungrounded_numbers",
            "clarification",
        }
    else:
        assert llm.calls == []  # Admin bị chặn trước khi gọi LLM


def test_admin_gets_403_even_when_the_llm_is_not_configured(
    api_client: TestClient, auth_headers: Headers, use_llm: Callable[..., None]
) -> None:
    use_llm(error=LLMNotConfigured("thiếu khoá"))

    assert ask(api_client, auth_headers(ADMIN)).status_code == 403


def test_open_screen_is_authorized_like_any_other_access(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: Callable[..., None],
    class_id_of: Callable[[str], int],
    subject_id_of: Callable[[str], int],
) -> None:
    llm = ScriptedLLM([says("Ok.")])
    use_llm(llm)

    own = ask(api_client, auth_headers(GVCN_11A2), class_id=class_id_of("11A2"))
    other_class = ask(api_client, auth_headers(GVCN_11A2), class_id=class_id_of("10A1"))
    other_subject = ask(
        api_client,
        auth_headers(GVBM_VAN_11),
        class_id=class_id_of("11A2"),
        subject_id=subject_id_of("Toán"),
    )

    assert own.status_code == 200
    assert other_class.status_code == 403 and other_subject.status_code == 403
    assert len(llm.calls) == 1


def test_open_class_that_does_not_exist_is_404_for_principal(
    api_client: TestClient, auth_headers: Headers, use_llm: Callable[..., None]
) -> None:
    use_llm(ScriptedLLM([]))

    assert ask(api_client, auth_headers(PRINCIPAL), class_id=999_999).status_code == 404


# --- Kiểm tra dữ liệu vào ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"question": ""},
        {"question": "   "},
        {"question": "x" * 1001},
        {"question": "ok", "semester": "3"},
        {"question": "ok", "subject_id": 1},  # môn phải đi kèm lớp
        {"question": "ok", "class_id": "abc"},
    ],
)
def test_chat_validates_the_request(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: Callable[..., None],
    payload: dict[str, Any],
) -> None:
    use_llm(ScriptedLLM([]))

    response = api_client.post(CHAT, json=payload, headers=auth_headers(GVCN_11A2))

    assert response.status_code == 422


# --- Lỗi cấu hình, nhà cung cấp, giới hạn -----------------------------------------------------


def test_not_configured_llm_is_503_with_a_plain_message(
    api_client: TestClient, auth_headers: Headers, use_llm: Callable[..., None]
) -> None:
    use_llm(error=LLMNotConfigured("Chưa đặt LLM_API_KEY"))

    response = ask(api_client, auth_headers(GVCN_11A2))

    assert response.status_code == 503
    assert "LLM_API_KEY" not in response.text  # không lộ chi tiết cấu hình cho giáo viên


def test_provider_failure_is_502_and_logged(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: Callable[..., None],
    db_session: Session,
) -> None:
    def fail(_messages: Any) -> Any:
        raise LLMError("sk-ant-bí-mật")

    use_llm(ScriptedLLM([fail]))

    response = ask(api_client, auth_headers(GVCN_11A2), "Tóm tắt lớp.")

    assert response.status_code == 502 and "sk-ant" not in response.text
    log = db_session.scalars(select(AiLog).order_by(AiLog.id.desc())).first()
    assert log is not None and log.error == "LLMError"


def test_rate_limit_is_429_with_retry_after(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.assistant.service.get_settings", lambda: SimpleNamespace(assistant_rate_per_minute=1)
    )
    use_llm(ScriptedLLM([says("Ok."), says("Ok.")]))

    first = ask(api_client, auth_headers(GVCN_11A2))
    second = ask(api_client, auth_headers(GVCN_11A2))
    other_user = ask(api_client, auth_headers(PRINCIPAL))

    assert first.status_code == 200
    assert second.status_code == 429 and second.headers["retry-after"] == "60"
    assert other_user.status_code == 200


# --- Nguồn trong phản hồi ---------------------------------------------------------------------


def test_sources_are_returned_with_their_types(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: Callable[..., None],
    class_id_of: Callable[[str], int],
    add_regulation: Callable[..., Any],
) -> None:
    add_regulation()
    llm = ScriptedLLM(
        [
            wants(
                call("get_class_summary"),
                call("search_regulation", query="đơn xin phép nghỉ học của cha mẹ học sinh"),
            ),
            says("Lớp có 40 học sinh. Nguồn: get_class_summary, Điều 1."),
        ]
    )
    use_llm(llm)

    body = ask(
        api_client, auth_headers(GVCN_11A2), "Tóm tắt lớp.", class_id=class_id_of("11A2")
    ).json()

    kinds = {s["type"] for s in body["sources"]}
    assert kinds == {"data", "regulation"}
    regulation = next(s for s in body["sources"] if s["type"] == "regulation")
    assert regulation["article"] == "Điều 1" and regulation["document"].startswith("Quy chế thử")
    assert body["ungrounded_numbers"] == []


def test_blocked_flag_reaches_the_client(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: Callable[..., None],
    class_id_of: Callable[[str], int],
) -> None:
    use_llm(
        ScriptedLLM(
            [
                wants(call("get_class_summary", class_id=class_id_of("10A1"))),
                says("Bạn không có quyền xem lớp đó."),
            ]
        )
    )

    body = ask(api_client, auth_headers(GVCN_11A2), "Số liệu lớp 10A1?").json()

    assert body["blocked"] is True


# --- Phản hồi đúng/sai ------------------------------------------------------------------------


def test_feedback_roles_and_validation(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: Callable[..., None],
    db_session: Session,
) -> None:
    use_llm(ScriptedLLM([says("Ok.")]))
    log_id = ask(api_client, auth_headers(GVCN_11A2)).json()["log_id"]
    url = f"/api/v1/assistant/logs/{log_id}/feedback"

    def rate(email: str | None, value: object) -> Any:
        headers = auth_headers(email) if email else {}
        return api_client.patch(url, json={"value": value}, headers=headers)

    assert rate(None, "correct").status_code == 401
    for other in (PRINCIPAL, GVBM_VAN_11, ADMIN):
        assert rate(other, "correct").status_code == 403
    assert rate(GVCN_11A2, "tuyệt vời").status_code == 422
    assert rate(GVCN_11A2, "incorrect").json() == {"log_id": log_id, "value": "incorrect"}
    assert db_session.get(AiLog, log_id).feedback is AssistantFeedback.INCORRECT  # type: ignore[union-attr]
    assert rate(GVCN_11A2, "correct").status_code == 200  # đổi ý được
    missing = api_client.patch(
        "/api/v1/assistant/logs/999999/feedback",
        json={"value": "correct"},
        headers=auth_headers(GVCN_11A2),
    )
    assert missing.status_code == 403  # cùng lỗi như không phải chủ nhân


def test_endpoints_are_in_the_openapi_document(client: TestClient) -> None:
    paths = client.get("/api/openapi.json").json()["paths"]

    assert "post" in paths["/api/v1/assistant/chat"]
    assert "patch" in paths["/api/v1/assistant/logs/{log_id}/feedback"]

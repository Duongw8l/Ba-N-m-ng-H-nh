"""API trợ lý AI (D-091): hỏi đáp và đánh giá câu trả lời.

Thứ tự lỗi: 401 chưa đăng nhập, 403 không được dùng trợ lý (Admin) hoặc không có quyền với lớp/môn
đang mở, rồi mới tới 503 (chưa cấu hình LLM: nhà cung cấp chỉ được dựng SAU khi kiểm quyền), 429
vượt giới hạn, 502 lỗi nhà cung cấp.
"""

import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.assistant import service
from app.assistant.llm import LLMError, LLMNotConfigured, LLMProvider
from app.assistant.providers import get_llm_provider
from app.assistant.schemas import ChatIn, ChatOut, FeedbackIn, FeedbackOut
from app.auth.deps import CurrentUser
from app.core.authorize import authorize_assistant
from app.core.db import DbSession
from app.rag.router import EmbedderDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["assistant"])

ProviderFactory = Callable[[], LLMProvider]


def get_provider_factory() -> ProviderFactory:
    """Dependency để test thay bằng LLM giả (app.dependency_overrides)."""
    return get_llm_provider


ProviderFactoryDep = Annotated[ProviderFactory, Depends(get_provider_factory)]


@router.post(
    "/assistant/chat",
    response_model=ChatOut,
    summary="Hỏi trợ lý AI (giáo viên và BGH); trả câu trả lời kèm nguồn",
)
def chat(
    body: ChatIn,
    user: CurrentUser,
    session: DbSession,
    provider_factory: ProviderFactoryDep,
    embedder: EmbedderDep,
) -> ChatOut:
    authorize_assistant(user)
    try:
        provider = provider_factory()
    except LLMNotConfigured as error:
        logger.warning("Trợ lý AI chưa được cấu hình: %s", error)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trợ lý AI chưa được cấu hình. Hãy báo quản trị viên.",
        ) from error

    request = service.ChatRequest(body.question, body.class_id, body.subject_id, body.semester)
    try:
        result = service.ask(session, user, provider, request, embedder=embedder)
    except service.RateLimited:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bạn hỏi hơi nhanh. Hãy đợi một lát rồi hỏi tiếp.",
            headers={"Retry-After": "60"},
        ) from None
    except service.ScreenNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except LLMError as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="Không gọi được mô hình ngôn ngữ lúc này. Hãy thử lại sau.",
        ) from error
    except service.UnsafeRequest as error:
        logger.error("Hàng rào ẩn danh chặn một lần gọi LLM")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error

    return ChatOut(
        log_id=result.log_id,
        answer=result.answer,
        sources=result.sources,  # type: ignore[arg-type]  # dict khớp một trong hai schema nguồn
        blocked=result.blocked,
        ungrounded_numbers=result.ungrounded_numbers,
        clarification=result.clarification,
    )


@router.patch(
    "/assistant/logs/{log_id}/feedback",
    response_model=FeedbackOut,
    summary="Đánh giá câu trả lời đúng hoặc sai (chỉ người đã hỏi)",
)
def feedback(log_id: int, body: FeedbackIn, user: CurrentUser, session: DbSession) -> FeedbackOut:
    value = service.set_feedback(session, user, log_id, body.value)
    return FeedbackOut(log_id=log_id, value=value)

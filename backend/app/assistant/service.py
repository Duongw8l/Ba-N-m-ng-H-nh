"""Vòng lặp hỏi đáp của trợ lý AI (Giai đoạn 8, D-089, D-091).

Một câu hỏi đi qua các bước của DESIGN mục 6.3 (FLOWS luồng 2):
1. kiểm quyền dùng trợ lý và quyền với lớp/môn đang mở, kiểm giới hạn số câu hỏi mỗi phút;
2. ẩn danh câu hỏi (họ tên, mã học sinh thành HS_01...); tên gọi trùng thì hỏi lại, không gọi LLM;
3. gửi LLM câu hỏi + bảy hàm được phép; chạy các hàm LLM chọn (tối đa 4 vòng, mỗi vòng tối đa
   `MAX_CALLS_PER_ROUND` hàm) trong transaction chỉ đọc; gửi kết quả (đã ẩn danh) lại cho LLM;
4. đổi mã tạm về họ tên thật, đính nguồn, kiểm số liệu, ghi `ai_logs` (bản đã ẩn danh).

Mỗi câu hỏi độc lập (không nhớ lượt trước), và bộ ẩn danh chỉ sống trong một lần gọi `ask`.
"""

import json
import re
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics import repository as repo
from app.analytics.config import load_config
from app.analytics.schemas import Period
from app.assistant.grounding import ungrounded_numbers
from app.assistant.llm import LLMError, LLMProvider, Message
from app.assistant.models import AiLog
from app.assistant.prompts import PROMPT_VERSION, load_system_prompt
from app.assistant.scope import ClassItem, load_roster, load_scope, scope_prompt
from app.assistant.tools import ToolContext, ToolOutcome, run_tool, tool_specs
from app.auth.models import User
from app.core.authorize import AuthorizationError, authorize, authorize_assistant
from app.core.config import get_settings
from app.core.enums import AssistantFeedback
from app.core.pseudonymize import Pseudonymizer, UnsafePayload
from app.rag.embedding import Embedder

MAX_ROUNDS = 4  # số vòng gọi hàm tối đa mỗi câu hỏi (PROMPTS Giai đoạn 8)
MAX_CALLS_PER_ROUND = 4
MAX_QUESTION_CHARS = 1000
MAX_RESULT_CHARS = 24_000
RATE_WINDOW = timedelta(seconds=60)
NO_ANSWER = "Trợ lý chưa tạo được câu trả lời. Bạn thử hỏi lại theo cách khác nhé."


class RateLimited(Exception):
    """Quá số câu hỏi cho phép trong một phút."""


class ScreenNotFound(LookupError):
    """Lớp hoặc môn đang mở không tồn tại (chỉ BGH tới được đây; giáo viên bị 403 trước)."""


class UnsafeRequest(RuntimeError):
    """Hàng rào ẩn danh chặn không cho gọi LLM (dữ liệu còn danh tính thật)."""


@dataclass(frozen=True)
class ChatRequest:
    question: str
    class_id: int | None = None  # lớp đang mở trên màn hình
    subject_id: int | None = None  # môn đang mở (cần đi kèm class_id)
    semester: Period | None = None  # kỳ đang xem


@dataclass(frozen=True)
class ChatResult:
    log_id: int
    answer: str  # đã đổi mã tạm về họ tên thật
    sources: list[dict[str, Any]]
    blocked: bool  # có hàm bị `authorize()` chặn
    ungrounded_numbers: list[str]  # số trong câu trả lời không đối chiếu được với kết quả hàm
    clarification: bool = False  # trợ lý hỏi lại (tên trùng), không gọi LLM


# --- Tiện ích ----------------------------------------------------------------------------------


def _recent_questions(session: Session, user_id: int) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(AiLog)
            .where(AiLog.user_id == user_id, AiLog.created_at >= func.now() - RATE_WINDOW)
        )
        or 0
    )


def _wrap(tool_name: str, result: dict[str, Any]) -> str:
    """Kết quả hàm gửi LLM, nằm trong thẻ <du_lieu>: nội dung trong thẻ là dữ liệu, không phải chỉ
    dẫn. Chuỗi "</" bị vô hiệu để dữ liệu (ví dụ điều khoản do Admin tải lên) không đóng thẻ sớm."""
    body = json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
    body = body.replace("</", "<\\/")
    if len(body) > MAX_RESULT_CHARS:
        body = json.dumps({"error": "result_too_large", "message": "Kết quả quá dài."})
    safe_name = re.sub(r"[^a-z_]", "", tool_name.lower())[:40]
    return f'<du_lieu ham="{safe_name}">{body}</du_lieu>'


def _open_screen(
    session: Session, user: User, request: ChatRequest
) -> tuple[ClassItem | None, tuple[int, str] | None]:
    """Lớp/môn đang mở trên màn hình: phải qua `authorize()` như mọi truy cập khác."""
    if request.class_id is None:
        return None, None
    authorize(session, user, class_id=request.class_id, subject_id=request.subject_id)
    info = repo.get_class(session, request.class_id)
    if info is None:
        raise ScreenNotFound("Không có lớp này.")
    subject = None
    if request.subject_id is not None:
        found = next(
            (s for s in repo.class_subjects(session, info.id) if s.id == request.subject_id), None
        )
        if found is None:
            raise ScreenNotFound("Lớp này không học môn đó.")
        subject = (found.id, found.name)
    return ClassItem(info.id, info.name, info.grade_level), subject


def _write_log(
    session: Session,
    *,
    user_id: int,
    question: str,
    tools_called: list[dict[str, Any]],
    answer: str | None,
    started: float,
    model: str,
    rounds: int,
    error: str | None = None,
) -> AiLog:
    log = AiLog(
        user_id=user_id,
        question=question,
        tools_called=tools_called,
        answer=answer,
        latency_ms=round((time.perf_counter() - started) * 1000),
        model=model,
        prompt_version=PROMPT_VERSION,
        rounds=rounds,
        error=error,
    )
    session.add(log)
    session.commit()
    return log


def _unique_sources(sources: list[dict[str, Any]], pseudo: Pseudonymizer) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for source in sources:
        shown = dict(source)
        if "description" in shown:
            shown["description"] = pseudo.depseudonymize(shown["description"])
        key = json.dumps(shown, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            unique.append(shown)
    return unique


# --- Hỏi đáp -----------------------------------------------------------------------------------


def ask(
    session: Session,
    user: User,
    provider: LLMProvider,
    request: ChatRequest,
    *,
    embedder: Embedder | None = None,
) -> ChatResult:
    """Trả lời một câu hỏi. Ném: AuthorizationError (403), RateLimited (429), ScreenNotFound (404),
    LLMError (502), UnsafeRequest (500). Lỗi gọi LLM vẫn được ghi vào ai_logs trước khi ném."""
    authorize_assistant(user)
    user_id = user.id
    scope = load_scope(session, user)
    open_class, open_subject = _open_screen(session, user, request)
    implicit_class = False
    if open_class is None and len(scope.classes) == 1:
        # Người hỏi chỉ có đúng một lớp (ví dụ GVCN thuần): lấy lớp đó làm mặc định để nhận ra tên
        # học sinh và để các hàm biết hỏi lớp nào, kể cả khi chưa mở màn hình của lớp.
        open_class, implicit_class = scope.classes[0], True
    if _recent_questions(session, user_id) >= get_settings().assistant_rate_per_minute:
        raise RateLimited

    started = time.perf_counter()
    semester: Period = request.semester or "1"
    roster_classes = [open_class.id] if open_class else scope.class_ids
    pseudo = Pseudonymizer(
        load_roster(session, roster_classes), open_class.id if open_class else None
    )
    question = pseudo.pseudonymize_question(request.question.strip())
    if question.ambiguous is not None:
        ambiguous = question.ambiguous
        answer = (
            f'Có {ambiguous.count} học sinh khớp "{ambiguous.name}". Bạn hãy nêu họ tên đầy đủ '
            "hoặc mã học sinh để tôi tra đúng em."
        )
        log = _write_log(
            session,
            user_id=user_id,
            question=question.text,
            tools_called=[],
            answer=answer,
            started=started,
            model="(không gọi LLM)",
            rounds=0,
        )
        return ChatResult(log.id, answer, [], False, [], clarification=True)

    ctx = ToolContext(
        session=session,
        user=user,
        pseudo=pseudo,
        config=load_config(session),
        class_id=open_class.id if open_class else None,
        subject_id=open_subject[0] if open_subject else None,
        semester=semester,
        embedder=embedder,
    )
    system = (
        load_system_prompt()
        + "\n\n"
        + scope_prompt(
            scope,
            open_class=open_class,
            open_subject=open_subject,
            semester=semester,
            implicit_class=implicit_class,
        )
    )
    messages = [Message("system", system), Message("user", question.text)]
    tools_called: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    evidence = [question.text]
    final_text: str | None = None
    rounds = 0
    failure: Exception | None = None

    try:
        ctx.begin_read_only()
        for turn in range(MAX_ROUNDS + 1):
            offer_tools = turn < MAX_ROUNDS  # sau vòng cuối: buộc trả lời bằng dữ liệu đã có
            pseudo.assert_safe(messages)  # hàng rào ẩn danh trước MỖI lần gọi LLM
            reply = provider.chat(messages, tool_specs() if offer_tools else [])
            if not reply.tool_calls or not offer_tools:
                final_text = reply.text
                break
            rounds += 1
            messages.append(Message("assistant", reply.text or "", reply.tool_calls, raw=reply.raw))
            for index, tool_call in enumerate(reply.tool_calls):
                began = time.perf_counter()
                if index >= MAX_CALLS_PER_ROUND:
                    outcome = ToolOutcome(
                        {"error": "too_many_calls", "message": "Quá nhiều hàm trong một lượt."},
                        ok=False,
                    )
                else:
                    outcome = run_tool(ctx, tool_call.name, tool_call.arguments)
                tools_called.append(
                    {
                        "name": tool_call.name,
                        "args": tool_call.arguments,
                        "ok": outcome.ok,
                        "blocked": outcome.blocked,
                        "ms": round((time.perf_counter() - began) * 1000),
                    }
                )
                content = _wrap(tool_call.name, outcome.result)
                evidence.append(content)
                sources.extend(outcome.sources)
                messages.append(
                    Message("tool", content, tool_call_id=tool_call.id, tool_name=tool_call.name)
                )
    except (LLMError, UnsafePayload) as error:
        failure = error
    finally:
        ctx.end_read_only()

    if failure is not None:
        _write_log(
            session,
            user_id=user_id,
            question=question.text,
            tools_called=tools_called,
            answer=None,
            started=started,
            model=provider.model,
            rounds=rounds,
            error=type(failure).__name__,
        )
        if isinstance(failure, UnsafePayload):
            raise UnsafeRequest("Không thể gửi dữ liệu cho mô hình ngôn ngữ một cách an toàn.")
        raise failure

    final_text = (final_text or "").strip() or NO_ANSWER
    log = _write_log(
        session,
        user_id=user_id,
        question=question.text,
        tools_called=tools_called,
        answer=final_text,
        started=started,
        model=provider.model,
        rounds=rounds,
    )
    return ChatResult(
        log_id=log.id,
        answer=pseudo.depseudonymize(final_text),
        sources=_unique_sources(sources, pseudo),
        blocked=any(call["blocked"] for call in tools_called),
        ungrounded_numbers=ungrounded_numbers(final_text, evidence),
    )


def set_feedback(
    session: Session, user: User, log_id: int, value: AssistantFeedback
) -> AssistantFeedback:
    """Người hỏi đánh giá câu trả lời đúng/sai. Chỉ chủ nhân dòng nhật ký; người khác nhận
    AuthorizationError (cùng 403 như không có dòng đó, để không lộ id nào có thật)."""
    authorize_assistant(user)
    log = session.get(AiLog, log_id)
    if log is None or log.user_id != user.id:
        raise AuthorizationError
    log.feedback = value
    session.commit()
    return value

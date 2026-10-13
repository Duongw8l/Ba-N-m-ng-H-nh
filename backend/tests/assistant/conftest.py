"""Fixture của test trợ lý AI: người dùng seed, ngữ cảnh gọi hàm, bộ nhúng giả và LLM giả.

Mọi test ở đây KHÔNG gọi LLM thật và không cần khoá API: `ScriptedLLM` trả các lượt trả lời đã định
sẵn và ghi lại mọi message nó nhận được, để test khẳng định dữ liệu gửi sang LLM không chứa họ tên
thật, ngày sinh hay thông tin phụ huynh.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics import repository as repo
from app.analytics.config import load_config
from app.analytics.schemas import Period
from app.assistant.llm import LLMReply, Message, ToolCall, ToolSpec
from app.assistant.tools import ToolContext
from app.auth.models import User
from app.core.pseudonymize import Pseudonymizer, RosterStudent
from app.rag.embedding import Embedder
from app.rag.service import IngestResult, ingest_document
from app.warning import service as warning_service
from tests.rag.conftest import SAMPLE_TEXT, HashingEmbedder


@pytest.fixture
def user_of(db_session: Session) -> Callable[[str], User]:
    def find(email: str) -> User:
        user = db_session.scalar(select(User).where(func.lower(User.email) == email.lower()))
        assert user is not None, email
        return user

    return find


@pytest.fixture
def alerts(db_session: Session, class_id_of: Callable[[str], int]) -> None:
    """Chạy cảnh báo sớm (chỉ lớp luật) cho lớp 11A2: dữ liệu seed của test chưa có risk_alerts."""
    warning_service.refresh_class(db_session, class_id_of("11A2"))


@pytest.fixture
def embedder() -> Embedder:
    return HashingEmbedder()


@pytest.fixture
def add_regulation(db_session: Session, embedder: Embedder) -> Callable[..., IngestResult]:
    def add(name: str = "Quy chế thử (VĂN BẢN GIẢ)", text: str = SAMPLE_TEXT) -> IngestResult:
        return ingest_document(
            db_session,
            name=name,
            file_name="quy-che.txt",
            data=text.encode(),
            embedder=embedder,
            user=None,
        )

    return add


def roster_of(session: Session, class_id: int) -> list[RosterStudent]:
    return [
        RosterStudent(s.student_id, class_id, s.full_name, s.student_code)
        for s in repo.class_students(session, class_id)
    ]


@pytest.fixture
def make_ctx(
    db_session: Session,
    user_of: Callable[[str], User],
    class_id_of: Callable[[str], int],
    subject_id_of: Callable[[str], int],
    embedder: Embedder,
) -> Callable[..., ToolContext]:
    """Ngữ cảnh gọi hàm cho một tài khoản seed. `roster` là các lớp mà bộ ẩn danh biết học sinh
    (mặc định lớp 11A2); `open_class`, `open_subject`, `semester` mô phỏng màn hình đang mở."""

    def build(
        email: str,
        *,
        open_class: str | None = None,
        open_subject: str | None = None,
        semester: Period = "1",
        roster: Sequence[str] = ("11A2",),
    ) -> ToolContext:
        students = [s for name in roster for s in roster_of(db_session, class_id_of(name))]
        open_class_id = class_id_of(open_class) if open_class else None
        return ToolContext(
            session=db_session,
            user=user_of(email),
            pseudo=Pseudonymizer(students, open_class_id),
            config=load_config(db_session),
            class_id=open_class_id,
            subject_id=subject_id_of(open_subject) if open_subject else None,
            semester=semester,
            embedder=embedder,
        )

    return build


# --- LLM giả -----------------------------------------------------------------------------------


@dataclass
class ScriptedLLM:
    """LLM giả: mỗi lần `chat` lấy một lượt trong kịch bản (hoặc gọi hàm sinh lượt từ tin nhắn).

    Ghi lại mọi lần gọi (`calls`) gồm các message và tên hàm được phép, để test quét nội dung.
    """

    script: list[LLMReply | Callable[[Sequence[Message]], LLMReply]]
    model: str = "llm-gia"
    calls: list[tuple[list[Message], list[str]]] = field(default_factory=list)

    def chat(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> LLMReply:
        self.calls.append((list(messages), [t.name for t in tools]))
        if not self.script:
            raise AssertionError("LLM giả hết kịch bản nhưng vẫn bị gọi thêm.")
        step = self.script.pop(0)
        return step(messages) if callable(step) else step

    def everything_sent(self) -> list[Message]:
        """Mọi message của mọi lần gọi (kể cả system prompt)."""
        return [message for messages, _tools in self.calls for message in messages]


def call(name: str, **arguments: Any) -> ToolCall:
    call.counter += 1  # type: ignore[attr-defined]
    return ToolCall(f"call_{call.counter}", name, arguments)  # type: ignore[attr-defined]


call.counter = 0  # type: ignore[attr-defined]


def says(text: str) -> LLMReply:
    return LLMReply(text, ())


def wants(*calls: ToolCall) -> LLMReply:
    return LLMReply(None, tuple(calls))

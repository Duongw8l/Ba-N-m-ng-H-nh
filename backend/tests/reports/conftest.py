"""Fixture của test nhận xét và báo cáo: LLM giả tự viết nhận xét trung tính theo các mã nhận được.

Mọi test ở đây KHÔNG gọi LLM thật và không cần khoá API. `FakeWriter` ghi lại mọi tin nhắn nó nhận
để test khẳng định dữ liệu gửi sang LLM không chứa họ tên, mã học sinh, ngày sinh, phụ huynh.
"""

import json
import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assistant.llm import LLMProvider, LLMReply, Message, ToolSpec
from app.assistant.router import get_provider_factory
from app.auth.models import User
from app.classes.models import Student
from app.main import app
from app.reports import jobs
from app.reports.router import get_job_runner

# Văn bản trung tính: không có chữ số (nên qua kiểm số liệu), không có từ cấm.
NEUTRAL = {
    "diem_manh": "Em học tập nghiêm túc và hoà đồng với thầy cô, bạn bè trong suốt học kỳ này.",
    "can_co_gang": "Em cần tiếp tục rèn luyện sự cẩn thận và kiên trì khi làm các bài tập khó.",
    "goi_y": "Gia đình có thể nhắc em duy trì thói quen ôn bài mỗi ngày và sắp xếp thời gian.",
}
BANNED = {
    "diem_manh": "Em học tập khá ổn định trong học kỳ này, có tiến bộ ở nhiều môn học.",
    "can_co_gang": "Em còn lười ôn bài và học yếu ở một số môn nên cần cố gắng nhiều hơn.",
    "goi_y": "Gia đình nên quan tâm đến việc học của em nhiều hơn trong thời gian tới đây.",
}

PAYLOAD = re.compile(r"<du_lieu>(.*?)</du_lieu>", re.DOTALL)


@dataclass
class FakeWriter:
    """LLM giả: mỗi mã học sinh trong dữ liệu nhận một nhận xét trung tính; báo cáo lớp / khối nhận
    một bản trung tính. `bad` là tập mã luôn bị viết bằng từ cấm (để thử viết lại)."""

    model: str = "llm-gia"
    bad: set[str] = field(default_factory=set)
    sections: dict[str, str] = field(default_factory=lambda: dict(NEUTRAL))
    calls: list[list[Message]] = field(default_factory=list)

    def chat(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> LLMReply:
        assert not tools, "Nhận xét và báo cáo không được cho LLM gọi hàm nào."
        self.calls.append(list(messages))
        user = next(m.content for m in messages if m.role == "user")
        match = PAYLOAD.search(user)
        assert match is not None, "Thiếu khối <du_lieu>"
        payload = json.loads(match.group(1).replace("<\\/", "</"))
        if user.startswith("Báo cáo cho"):
            return LLMReply(json.dumps(self.sections, ensure_ascii=False), ())
        entries = {code: BANNED if code in self.bad else self.sections for code in payload}
        return LLMReply(json.dumps(entries, ensure_ascii=False), ())

    def sent(self) -> str:
        """Mọi tin nhắn của mọi lần gọi, nối thành một chuỗi thường để quét."""
        return " ".join(m.content for call in self.calls for m in call).casefold()


class FailingWriter:
    model = "llm-hong"

    def __init__(self, error: Exception) -> None:
        self.error = error

    def chat(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> LLMReply:
        raise self.error


@pytest.fixture
def use_llm(api_client: TestClient) -> Iterator[Callable[..., None]]:
    """Cài LLM giả (hoặc lỗi cấu hình) cho các API nhận xét; api_client tự xoá override."""

    def install(llm: LLMProvider | None = None, *, error: Exception | None = None) -> None:
        def factory() -> LLMProvider:
            if error is not None:
                raise error
            assert llm is not None
            return llm

        app.dependency_overrides[get_provider_factory] = lambda: factory

    yield install


@pytest.fixture
def user_of(db_session: Session) -> Callable[[str], User]:
    def find(email: str) -> User:
        user = db_session.scalar(select(User).where(func.lower(User.email) == email.lower()))
        assert user is not None, email
        return user

    return find


@pytest.fixture
def student_id_of(db_session: Session) -> Callable[[str], int]:
    def find(code: str) -> int:
        student_id = db_session.scalar(select(Student.id).where(Student.student_code == code))
        assert student_id is not None, code
        return student_id

    return find


class BorrowedSession:
    """Đưa `db_session` cho luồng nền như một context manager (không đóng, không tạo mới)."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def __enter__(self) -> Session:
        return self.session

    def __exit__(self, *exc_info: object) -> None:
        return None


@dataclass
class JobQueue:
    """Runner giả: nhận việc nhưng chưa chạy. Test gọi `run()` đúng lúc để xem trạng thái đang chạy,
    hoặc chạy xong rồi mới xem. Chạy ngay trong luồng của test với `db_session`."""

    session: Session
    pending: list[tuple[int, LLMProvider]] = field(default_factory=list)

    def __call__(self, job_id: int, provider: LLMProvider) -> None:
        self.pending.append((job_id, provider))

    def run(self) -> int:
        ran = 0
        while self.pending:
            job_id, provider = self.pending.pop(0)
            jobs.run_job(job_id, provider, lambda: BorrowedSession(self.session))
            ran += 1
        return ran


@pytest.fixture
def job_queue(api_client: TestClient, db_session: Session) -> JobQueue:
    queue = JobQueue(db_session)
    app.dependency_overrides[get_job_runner] = lambda: queue
    return queue


def as_dict(response: Any) -> dict[str, Any]:
    body: dict[str, Any] = response.json()
    return body

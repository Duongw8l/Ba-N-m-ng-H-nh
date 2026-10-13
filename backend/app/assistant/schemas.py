"""Schema request/response của API trợ lý AI."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.analytics.schemas import Period
from app.core.enums import AssistantFeedback

MAX_QUESTION_CHARS = 1000


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    # Màn hình đang mở (khung chat tự biết): lớp, môn, kỳ. Phải qua authorize() như mọi truy cập.
    class_id: int | None = None
    subject_id: int | None = None
    semester: Period | None = None

    @field_validator("question")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Câu hỏi để trống.")
        return value

    @model_validator(mode="after")
    def _subject_needs_class(self) -> "ChatIn":
        if self.subject_id is not None and self.class_id is None:
            raise ValueError("subject_id phải đi kèm class_id.")
        return self


class DataSourceOut(BaseModel):
    """Nguồn số liệu: một hàm Analytics đã được gọi."""

    type: Literal["data"]
    tool: str
    description: str


class RegulationSourceOut(BaseModel):
    """Nguồn quy định: một điều khoản đã được tra."""

    type: Literal["regulation"]
    document: str
    article: str | None
    clause: str | None
    similarity: float


class ChatOut(BaseModel):
    log_id: int
    answer: str
    sources: list[Annotated[DataSourceOut | RegulationSourceOut, Field(discriminator="type")]]
    blocked: bool  # có hàm bị từ chối vì không đủ quyền
    ungrounded_numbers: list[str]  # số trong câu trả lời chưa đối chiếu được với kết quả hàm
    clarification: bool  # trợ lý hỏi lại (ví dụ trùng tên), chưa gọi mô hình


class FeedbackIn(BaseModel):
    value: AssistantFeedback


class FeedbackOut(BaseModel):
    log_id: int
    value: AssistantFeedback

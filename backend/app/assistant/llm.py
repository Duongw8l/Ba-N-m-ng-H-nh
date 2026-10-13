"""Giao diện chung của nhà cung cấp LLM (Giai đoạn 8, D-085).

Phần còn lại của trợ lý chỉ biết các kiểu ở đây; mỗi nhà cung cấp (Anthropic, Ollama) tự đổi sang
định dạng riêng của SDK. Đổi nhà cung cấp chỉ cần đổi `LLM_PROVIDER`, không sửa mã khác.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Role = Literal["system", "user", "assistant", "tool"]


class LLMNotConfigured(RuntimeError):
    """Chưa cấu hình LLM (thiếu LLM_PROVIDER, khoá API hoặc tên mô hình). API trả 503."""


class LLMError(RuntimeError):
    """Gọi LLM thất bại (mạng, hết hạn mức, phản hồi hỏng...). API trả 502."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolSpec:
    """Một hàm LLM được phép gọi. `input_schema` là JSON Schema của tham số."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()  # role "assistant": các hàm LLM đã đòi gọi
    tool_call_id: str | None = None  # role "tool": trả lời cho lệnh gọi nào
    tool_name: str | None = None  # role "tool": tên hàm (Ollama, Gemini cần)
    # Dữ liệu gốc của nhà cung cấp để gửi lại nguyên vẹn (Gemini bắt giữ "chữ ký suy nghĩ" của lượt
    # trả lời có gọi hàm). Mã chung không đọc trường này.
    raw: Any = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class LLMReply:
    """Một lượt trả lời của LLM: hoặc văn bản, hoặc yêu cầu gọi hàm (có thể cả hai)."""

    text: str | None
    tool_calls: tuple[ToolCall, ...]
    raw: Any = field(default=None, compare=False, repr=False)  # xem Message.raw


class LLMProvider(Protocol):
    model: str

    def chat(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> LLMReply:
        """Gửi hội thoại và các hàm được phép; `tools` rỗng thì LLM chỉ được trả lời bằng chữ."""
        ...

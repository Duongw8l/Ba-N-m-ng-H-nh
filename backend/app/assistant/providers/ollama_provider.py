"""Mô hình mở chạy nội bộ qua Ollama, dùng SDK chính thức `ollama` (D-085).

Dữ liệu không rời máy. Mô hình cần hỗ trợ gọi hàm (loại 7 đến 8B). Ollama không cấp id cho lệnh gọi
hàm nên id được tạo tại đây theo thứ tự (`call_0`, `call_1`...); kết quả hàm được ghép lại bằng tên
hàm.
"""

import logging
from collections.abc import Sequence
from typing import Any

from app.assistant.llm import LLMError, LLMReply, Message, ToolCall, ToolSpec

logger = logging.getLogger(__name__)


def to_ollama_messages(messages: Sequence[Message]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for message in messages:
        entry: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.role == "assistant" and message.tool_calls:
            entry["tool_calls"] = [
                {"function": {"name": call.name, "arguments": call.arguments}}
                for call in message.tool_calls
            ]
        if message.role == "tool" and message.tool_name:
            entry["tool_name"] = message.tool_name
        result.append(entry)
    return result


def to_ollama_tools(tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.input_schema,
            },
        }
        for t in tools
    ]


class OllamaProvider:
    def __init__(self, host: str, model: str, timeout: float = 60.0, client: Any = None) -> None:
        self.model = model
        if client is None:
            import ollama

            client = ollama.Client(host=host, timeout=timeout)
        self._client = client

    def chat(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> LLMReply:
        try:
            response = self._client.chat(
                model=self.model,
                messages=to_ollama_messages(messages),
                tools=to_ollama_tools(tools) if tools else None,
            )
        except Exception as error:  # noqa: BLE001 - mọi lỗi SDK/mạng đều thành LLMError
            logger.exception("Gọi Ollama thất bại")
            raise LLMError(f"Không gọi được mô hình ngôn ngữ ({type(error).__name__}).") from error

        reply = response.message
        calls = tuple(
            ToolCall(f"call_{index}", call.function.name, dict(call.function.arguments or {}))
            for index, call in enumerate(reply.tool_calls or [])
        )
        text = (reply.content or "").strip() or None
        if text is None and not calls:
            raise LLMError("Mô hình ngôn ngữ trả về phản hồi rỗng.")
        return LLMReply(text, calls)

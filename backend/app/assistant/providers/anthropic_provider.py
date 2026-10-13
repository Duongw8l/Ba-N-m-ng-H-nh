"""Nhà cung cấp API: Anthropic Claude, qua SDK chính thức `anthropic` (D-085).

Đổi định dạng trung lập (llm.py) sang định dạng Messages API: `system` tách riêng, lệnh gọi hàm là
khối `tool_use`, kết quả hàm là khối `tool_result` nằm trong MỘT message người dùng cho mỗi lượt gọi
hàm.
"""

import logging
from collections.abc import Sequence
from typing import Any

from app.assistant.llm import LLMError, LLMReply, Message, ToolCall, ToolSpec

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 2048


def to_anthropic_messages(messages: Sequence[Message]) -> tuple[str, list[dict[str, Any]]]:
    """(system, messages) theo Messages API. Các kết quả hàm liên tiếp gộp vào một message."""
    system_parts: list[str] = []
    result: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "system":
            system_parts.append(message.content)
        elif message.role == "user":
            result.append({"role": "user", "content": message.content})
        elif message.role == "assistant":
            blocks: list[dict[str, Any]] = []
            if message.content:
                blocks.append({"type": "text", "text": message.content})
            blocks += [
                {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
                for call in message.tool_calls
            ]
            result.append({"role": "assistant", "content": blocks or message.content})
        else:  # tool
            block = {
                "type": "tool_result",
                "tool_use_id": message.tool_call_id,
                "content": message.content,
            }
            previous = result[-1] if result else None
            if (
                previous is not None
                and previous["role"] == "user"
                and isinstance(previous["content"], list)
            ):
                previous["content"].append(block)
            else:
                result.append({"role": "user", "content": [block]})
    return "\n\n".join(system_parts), result


def to_anthropic_tools(tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in tools
    ]


class AnthropicProvider:
    def __init__(
        self, api_key: str, model: str = DEFAULT_MODEL, timeout: float = 60.0, client: Any = None
    ) -> None:
        self.model = model or DEFAULT_MODEL
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)
        self._client = client

    def chat(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> LLMReply:
        system, payload = to_anthropic_messages(messages)
        kwargs: dict[str, Any] = {}
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = to_anthropic_tools(tools)
        try:
            response = self._client.messages.create(
                model=self.model, max_tokens=MAX_TOKENS, messages=payload, **kwargs
            )
        except Exception as error:  # noqa: BLE001 - mọi lỗi SDK/mạng đều thành LLMError
            logger.exception("Gọi Anthropic thất bại")
            raise LLMError(f"Không gọi được mô hình ngôn ngữ ({type(error).__name__}).") from error

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(block.id, block.name, dict(block.input)))
        text = "".join(text_parts).strip() or None
        if text is None and not calls:
            raise LLMError("Mô hình ngôn ngữ trả về phản hồi rỗng.")
        return LLMReply(text, tuple(calls))

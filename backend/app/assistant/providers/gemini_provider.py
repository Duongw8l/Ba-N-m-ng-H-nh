"""Nhà cung cấp API: Google Gemini, qua SDK chính thức `google-genai` (D-094).

Đổi định dạng trung lập (llm.py) sang `Content`/`Part` của Gemini: lệnh gọi hàm là `function_call`,
kết quả hàm là `function_response`, mọi kết quả của một lượt gom vào MỘT Content vai trò user.

Lượt trả lời có gọi hàm của mô hình được gửi lại NGUYÊN VẸN qua `Message.raw` (không dựng lại từ
`ToolCall`): các mô hình Gemini mới gắn "chữ ký suy nghĩ" vào phần gọi hàm và đòi nhận lại đúng chữ
ký đó ở lượt kế tiếp, nếu không API trả lỗi 400.
"""

import logging
import re
import time
from collections.abc import Sequence
from typing import Any

from google.genai import types

from app.assistant.llm import LLMError, LLMReply, Message, ToolCall, ToolSpec

logger = logging.getLogger(__name__)

# Bí danh luôn trỏ tới Flash mới nhất: tên cụ thể bị gỡ khá nhanh (gemini-2.5-flash đã không còn cho
# tài khoản mới). Muốn cố định thì đặt LLM_MODEL. Dòng Pro cần gói trả phí (gói miễn phí hạn mức 0).
DEFAULT_MODEL = "gemini-flash-latest"
RETRY_STATUS_CODES = (500, 502, 503, 504)  # lỗi tạm thời ("high demand"), khác 429
RETRY_ATTEMPTS = 4
# Hết hạn mức theo phút (gói miễn phí chỉ vài yêu cầu mỗi phút): Google nói rõ chờ bao lâu ("retry
# in 44s"). Chờ rồi thử lại nếu thời gian đó không quá dài; hết hạn mức theo ngày hay mô hình không
# có hạn mức (Pro trên gói miễn phí) thì không có thời gian chờ ngắn nên báo lỗi ngay.
MAX_QUOTA_WAIT_SECONDS = 75.0
QUOTA_RETRIES = 3
# Mô hình "suy nghĩ" tính cả token suy nghĩ vào giới hạn đầu ra, nên để dư.
MAX_OUTPUT_TOKENS = 4096


def _clean_schema(schema: Any) -> Any:
    """Bỏ `additionalProperties` (Gemini không nhận trường này trong schema hàm)."""
    if isinstance(schema, dict):
        return {k: _clean_schema(v) for k, v in schema.items() if k != "additionalProperties"}
    if isinstance(schema, list):
        return [_clean_schema(item) for item in schema]
    return schema


def quota_wait_seconds(error: Exception) -> float | None:
    """Số giây Google yêu cầu chờ trước khi gọi lại một lỗi 429 (RetryInfo), hoặc None."""
    if getattr(error, "code", None) != 429:
        return None
    details = getattr(error, "details", None)
    body = details.get("error", details) if isinstance(details, dict) else {}
    for item in body.get("details", []) if isinstance(body, dict) else []:
        delay = item.get("retryDelay") if isinstance(item, dict) else None
        match = re.fullmatch(r"(\d+(?:\.\d+)?)s", delay or "")
        if match:
            return float(match.group(1)) + 1.0
    return None


def to_gemini_tools(tools: Sequence[ToolSpec]) -> list[types.Tool]:
    if not tools:
        return []
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=t.name,
                    description=t.description,
                    parameters_json_schema=_clean_schema(t.input_schema),
                )
                for t in tools
            ]
        )
    ]


def to_gemini_contents(messages: Sequence[Message]) -> tuple[str, list[types.Content]]:
    """(system_instruction, contents). Các kết quả hàm liên tiếp gộp vào một Content."""
    system_parts: list[str] = []
    contents: list[types.Content] = []
    tool_turn: types.Content | None = None  # Content kết quả hàm đang được gom
    for message in messages:
        if message.role != "tool":
            tool_turn = None
        if message.role == "system":
            system_parts.append(message.content)
        elif message.role == "user":
            contents.append(types.Content(role="user", parts=[types.Part(text=message.content)]))
        elif message.role == "assistant":
            if message.raw is not None:
                contents.append(message.raw)
                continue
            parts: list[types.Part] = []
            if message.content:
                parts.append(types.Part(text=message.content))
            parts += [
                types.Part(function_call=types.FunctionCall(name=c.name, args=c.arguments))
                for c in message.tool_calls
            ]
            contents.append(types.Content(role="model", parts=parts))
        else:  # tool
            part = types.Part(
                function_response=types.FunctionResponse(
                    name=message.tool_name or "", response={"output": message.content}
                )
            )
            if tool_turn is None:
                tool_turn = types.Content(role="user", parts=[part])
                contents.append(tool_turn)
            else:
                tool_turn.parts = [*(tool_turn.parts or []), part]
    return "\n\n".join(system_parts), contents


class GeminiProvider:
    def __init__(
        self, api_key: str, model: str = DEFAULT_MODEL, timeout: float = 60.0, client: Any = None
    ) -> None:
        self.model = model or DEFAULT_MODEL
        self._timeout_ms = int(timeout * 1000)
        if client is None:
            from google import genai

            client = genai.Client(api_key=api_key)
        self._client = client

    def chat(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> LLMReply:
        system, contents = to_gemini_contents(messages)
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            tools=to_gemini_tools(tools) or None,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            # Chỉ để mã của ta chạy hàm (qua authorize), không để SDK tự gọi.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            http_options=types.HttpOptions(
                timeout=self._timeout_ms,
                retry_options=types.HttpRetryOptions(
                    attempts=RETRY_ATTEMPTS, http_status_codes=list(RETRY_STATUS_CODES)
                ),
            ),
        )
        response = None
        for attempt in range(QUOTA_RETRIES + 1):
            try:
                response = self._client.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
                break
            except Exception as error:  # noqa: BLE001 - mọi lỗi SDK/mạng đều thành LLMError
                wait = quota_wait_seconds(error)
                if wait is not None and wait <= MAX_QUOTA_WAIT_SECONDS and attempt < QUOTA_RETRIES:
                    logger.warning("Gemini hết hạn mức theo phút, chờ %.0f giây rồi thử lại", wait)
                    time.sleep(wait)
                    continue
                logger.exception("Gọi Gemini thất bại")
                code = getattr(error, "code", None)
                suffix = f", mã {code}" if isinstance(code, int) else ""
                raise LLMError(
                    f"Không gọi được mô hình ngôn ngữ ({type(error).__name__}{suffix})."
                ) from error
        assert response is not None

        candidates = response.candidates or []
        content = candidates[0].content if candidates else None
        if content is None or not content.parts:
            raise LLMError("Mô hình ngôn ngữ trả về phản hồi rỗng hoặc bị chặn.")
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for part in content.parts:
            if part.function_call is not None and part.function_call.name:
                call = part.function_call
                calls.append(
                    ToolCall(
                        call.id or f"call_{len(calls)}", call.name or "", dict(call.args or {})
                    )
                )
            elif part.text and not part.thought:
                text_parts.append(part.text)
        text = "".join(text_parts).strip() or None
        if text is None and not calls:
            raise LLMError("Mô hình ngôn ngữ trả về phản hồi rỗng.")
        return LLMReply(text, tuple(calls), raw=content)

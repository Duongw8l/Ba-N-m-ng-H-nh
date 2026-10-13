"""LLMProvider: đổi định dạng trung lập sang Anthropic và Ollama, chọn nhà cung cấp theo cấu hình
(D-085). Dùng client SDK giả nên không cần mạng và không cần khoá API."""

from types import SimpleNamespace
from typing import Any

import pytest

from app.assistant.llm import LLMError, LLMNotConfigured, Message, ToolCall, ToolSpec
from app.assistant.providers import build_provider
from app.assistant.providers.anthropic_provider import (
    DEFAULT_MODEL,
    AnthropicProvider,
    to_anthropic_messages,
    to_anthropic_tools,
)
from app.assistant.providers.gemini_provider import (
    DEFAULT_MODEL as GEMINI_DEFAULT_MODEL,
)
from app.assistant.providers.gemini_provider import (
    MAX_QUOTA_WAIT_SECONDS,
    GeminiProvider,
    quota_wait_seconds,
    to_gemini_contents,
    to_gemini_tools,
)
from app.assistant.providers.ollama_provider import (
    OllamaProvider,
    to_ollama_messages,
    to_ollama_tools,
)
from app.core.config import Settings

SPEC = ToolSpec(
    "get_class_summary",
    "Tổng hợp một lớp.",
    {"type": "object", "properties": {"semester": {"type": "string"}}},
)
CALL = ToolCall("toolu_1", "get_class_summary", {"semester": "1"})
CONVERSATION = [
    Message("system", "Bạn là trợ lý."),
    Message("user", "Lớp có bao nhiêu em?"),
    Message("assistant", "", (CALL, ToolCall("toolu_2", "list_students", {}))),
    Message("tool", '{"n": 40}', tool_call_id="toolu_1", tool_name="get_class_summary"),
    Message("tool", '{"n": 3}', tool_call_id="toolu_2", tool_name="list_students"),
]


# --- Anthropic ---------------------------------------------------------------------------------


def test_anthropic_messages_split_system_and_group_tool_results() -> None:
    system, messages = to_anthropic_messages(CONVERSATION)

    assert system == "Bạn là trợ lý."
    assert messages[0] == {"role": "user", "content": "Lớp có bao nhiêu em?"}
    assert messages[1] == {
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "get_class_summary",
                "input": {"semester": "1"},
            },
            {"type": "tool_use", "id": "toolu_2", "name": "list_students", "input": {}},
        ],
    }
    # Hai kết quả của cùng một lượt nằm trong MỘT message người dùng.
    assert messages[2] == {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_1", "content": '{"n": 40}'},
            {"type": "tool_result", "tool_use_id": "toolu_2", "content": '{"n": 3}'},
        ],
    }
    assert len(messages) == 3


def test_anthropic_assistant_text_and_tool_use_share_one_message() -> None:
    _system, messages = to_anthropic_messages([Message("assistant", "Để tôi tra.", (CALL,))])

    assert messages[0]["content"][0] == {"type": "text", "text": "Để tôi tra."}
    assert messages[0]["content"][1]["type"] == "tool_use"


def test_anthropic_tools_use_input_schema() -> None:
    assert to_anthropic_tools([SPEC]) == [
        {"name": SPEC.name, "description": SPEC.description, "input_schema": SPEC.input_schema}
    ]


class FakeAnthropic:
    def __init__(self, content: list[Any] | None = None, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._content = content if content is not None else []
        self._error = error
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return SimpleNamespace(content=self._content)


def text_block(text: str) -> Any:
    return SimpleNamespace(type="text", text=text)


def tool_block(id_: str, name: str, input_: dict[str, Any]) -> Any:
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=input_)


def test_anthropic_returns_text() -> None:
    client = FakeAnthropic([text_block("Lớp có "), text_block("40 em.")])
    provider = AnthropicProvider("khoa", client=client)

    reply = provider.chat(CONVERSATION[:2], [SPEC])

    assert reply.text == "Lớp có 40 em."
    assert reply.tool_calls == ()
    sent = client.calls[0]
    assert sent["model"] == DEFAULT_MODEL
    assert sent["system"] == "Bạn là trợ lý."
    assert sent["tools"][0]["name"] == "get_class_summary"
    assert sent["max_tokens"] > 0


def test_anthropic_returns_tool_calls() -> None:
    client = FakeAnthropic([text_block("Tra đã."), tool_block("t1", "list_students", {"x": 1})])

    reply = AnthropicProvider("khoa", client=client).chat(CONVERSATION[:2], [SPEC])

    assert reply.tool_calls == (ToolCall("t1", "list_students", {"x": 1}),)


def test_anthropic_without_tools_sends_no_tools_field() -> None:
    client = FakeAnthropic([text_block("ok")])

    AnthropicProvider("khoa", client=client).chat(CONVERSATION[:2], [])

    assert "tools" not in client.calls[0]


def test_anthropic_model_comes_from_configuration() -> None:
    assert (
        AnthropicProvider("khoa", "claude-haiku-5-5", client=FakeAnthropic()).model
        == "claude-haiku-5-5"
    )
    assert AnthropicProvider("khoa", "", client=FakeAnthropic()).model == DEFAULT_MODEL


def test_anthropic_sdk_error_becomes_llm_error_without_leaking_details() -> None:
    client = FakeAnthropic(error=RuntimeError("sk-ant-bí-mật không được lộ"))

    with pytest.raises(LLMError) as raised:
        AnthropicProvider("khoa", client=client).chat(CONVERSATION[:2], [SPEC])

    assert "sk-ant" not in str(raised.value)


def test_anthropic_empty_response_is_an_error() -> None:
    with pytest.raises(LLMError):
        AnthropicProvider("khoa", client=FakeAnthropic([])).chat(CONVERSATION[:2], [SPEC])


# --- Ollama ------------------------------------------------------------------------------------


def test_ollama_messages_and_tools() -> None:
    messages = to_ollama_messages(CONVERSATION)

    assert messages[0] == {"role": "system", "content": "Bạn là trợ lý."}
    assert messages[2]["tool_calls"][0] == {
        "function": {"name": "get_class_summary", "arguments": {"semester": "1"}}
    }
    assert messages[3] == {"role": "tool", "content": '{"n": 40}', "tool_name": "get_class_summary"}
    assert to_ollama_tools([SPEC]) == [
        {
            "type": "function",
            "function": {
                "name": SPEC.name,
                "description": SPEC.description,
                "parameters": SPEC.input_schema,
            },
        }
    ]


class FakeOllama:
    def __init__(self, message: Any = None, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._message = message
        self._error = error

    def chat(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return SimpleNamespace(message=self._message)


def ollama_call(name: str, arguments: dict[str, Any]) -> Any:
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))


def test_ollama_returns_text_and_tool_calls_with_generated_ids() -> None:
    message = SimpleNamespace(
        content="Đang tra.",
        tool_calls=[
            ollama_call("get_class_summary", {"semester": "2"}),
            ollama_call("list_students", {}),
        ],
    )
    client = FakeOllama(message)

    reply = OllamaProvider("http://x", "qwen2.5:7b", client=client).chat(CONVERSATION[:2], [SPEC])

    assert reply.text == "Đang tra."
    assert [(c.id, c.name, c.arguments) for c in reply.tool_calls] == [
        ("call_0", "get_class_summary", {"semester": "2"}),
        ("call_1", "list_students", {}),
    ]
    assert client.calls[0]["model"] == "qwen2.5:7b"
    assert client.calls[0]["tools"][0]["function"]["name"] == "get_class_summary"


def test_ollama_without_tools_sends_none() -> None:
    client = FakeOllama(SimpleNamespace(content="ok", tool_calls=None))

    OllamaProvider("http://x", "m", client=client).chat(CONVERSATION[:2], [])

    assert client.calls[0]["tools"] is None


def test_ollama_errors_and_empty_replies_become_llm_error() -> None:
    with pytest.raises(LLMError):
        OllamaProvider("http://x", "m", client=FakeOllama(error=ConnectionError("tắt"))).chat(
            CONVERSATION[:2], []
        )
    with pytest.raises(LLMError):
        OllamaProvider(
            "http://x", "m", client=FakeOllama(SimpleNamespace(content="", tool_calls=None))
        ).chat(CONVERSATION[:2], [])


# --- Gemini ------------------------------------------------------------------------------------


def test_gemini_contents_split_system_and_group_function_responses() -> None:
    system, contents = to_gemini_contents(CONVERSATION)

    assert system == "Bạn là trợ lý."
    assert [c.role for c in contents] == ["user", "model", "user"]
    assert contents[0].parts[0].text == "Lớp có bao nhiêu em?"
    calls = [p.function_call for p in contents[1].parts]
    assert [(c.name, dict(c.args)) for c in calls] == [
        ("get_class_summary", {"semester": "1"}),
        ("list_students", {}),
    ]
    # Hai kết quả của cùng một lượt nằm trong MỘT Content người dùng, ghép theo tên hàm.
    responses = [p.function_response for p in contents[2].parts]
    assert [(r.name, r.response) for r in responses] == [
        ("get_class_summary", {"output": '{"n": 40}'}),
        ("list_students", {"output": '{"n": 3}'}),
    ]


def test_gemini_resends_the_models_own_turn_untouched_to_keep_thought_signatures() -> None:
    from google.genai import types

    original = types.Content(
        role="model",
        parts=[
            types.Part(
                function_call=types.FunctionCall(name="list_students", args={}),
                thought_signature=b"chu-ky-suy-nghi",
            )
        ],
    )
    messages = [
        Message("user", "Hỏi."),
        Message("assistant", "", (ToolCall("c", "list_students", {}),), raw=original),
        Message("tool", "{}", tool_call_id="c", tool_name="list_students"),
    ]

    _system, contents = to_gemini_contents(messages)

    assert contents[1] is original
    assert contents[1].parts[0].thought_signature == b"chu-ky-suy-nghi"


def test_gemini_tools_drop_additional_properties_and_keep_the_rest() -> None:
    from app.assistant.tools import tool_specs

    declarations = to_gemini_tools(tool_specs())[0].function_declarations

    assert len(declarations) == 7
    for declaration in declarations:
        assert "additionalProperties" not in str(declaration.parameters_json_schema)
        assert declaration.parameters_json_schema["type"] == "object"
    assert to_gemini_tools([]) == []


class FakeGemini:
    def __init__(self, parts: list[Any] | None = None, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._parts = parts
        self._error = error
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        if self._parts is None:
            return SimpleNamespace(candidates=[])
        content = SimpleNamespace(role="model", parts=self._parts)
        return SimpleNamespace(candidates=[SimpleNamespace(content=content)])


def gem_text(text: str, thought: bool = False) -> Any:
    return SimpleNamespace(text=text, thought=thought, function_call=None)


def gem_call(name: str, args: dict[str, Any], call_id: str | None = None) -> Any:
    return SimpleNamespace(
        text=None, thought=None, function_call=SimpleNamespace(name=name, args=args, id=call_id)
    )


def test_gemini_returns_text_and_ignores_thought_parts() -> None:
    client = FakeGemini([gem_text("Đang nghĩ…", thought=True), gem_text("Lớp có 40 em.")])

    reply = GeminiProvider("khoa", client=client).chat(CONVERSATION[:2], [SPEC])

    assert reply.text == "Lớp có 40 em." and reply.tool_calls == ()
    sent = client.calls[0]
    assert sent["model"] == GEMINI_DEFAULT_MODEL
    assert sent["config"].system_instruction == "Bạn là trợ lý."
    assert sent["config"].tools[0].function_declarations[0].name == "get_class_summary"
    assert sent["config"].automatic_function_calling.disable is True


def test_gemini_returns_tool_calls_and_keeps_the_raw_turn() -> None:
    client = FakeGemini(
        [gem_call("list_students", {"x": 1}), gem_call("get_class_summary", {}, "id9")]
    )

    reply = GeminiProvider("khoa", client=client).chat(CONVERSATION[:2], [SPEC])

    assert [(c.id, c.name, c.arguments) for c in reply.tool_calls] == [
        ("call_0", "list_students", {"x": 1}),
        ("id9", "get_class_summary", {}),
    ]
    assert reply.raw is not None and len(reply.raw.parts) == 2


def test_gemini_without_tools_sends_none_and_model_comes_from_configuration() -> None:
    client = FakeGemini([gem_text("ok")])
    provider = GeminiProvider("khoa", "gemini-3.1-pro-preview", client=client)

    provider.chat(CONVERSATION[:2], [])

    assert provider.model == "gemini-3.1-pro-preview"
    assert client.calls[0]["config"].tools is None
    assert GeminiProvider("khoa", "", client=client).model == GEMINI_DEFAULT_MODEL


def test_gemini_retries_only_transient_server_errors() -> None:
    client = FakeGemini([gem_text("ok")])

    GeminiProvider("khoa", client=client).chat(CONVERSATION[:2], [])

    retry = client.calls[0]["config"].http_options.retry_options
    assert set(retry.http_status_codes) == {500, 502, 503, 504} and retry.attempts >= 2


class QuotaError(Exception):
    def __init__(self, delay: str | None, code: int = 429) -> None:
        super().__init__("hết hạn mức")
        self.code = code
        details = [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": delay}]
        self.details = {"error": {"code": code, "details": details if delay else []}}


class FlakyGemini:
    """Hết hạn mức theo phút `failures` lần rồi mới trả lời."""

    def __init__(self, failures: int, delay: str | None) -> None:
        self.calls = 0
        self._failures, self._delay = failures, delay
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, **_kwargs: Any) -> Any:
        self.calls += 1
        if self.calls <= self._failures:
            raise QuotaError(self._delay)
        content = SimpleNamespace(role="model", parts=[gem_text("Xong.")])
        return SimpleNamespace(candidates=[SimpleNamespace(content=content)])


def test_quota_wait_is_read_from_the_retry_info_and_only_for_429() -> None:
    assert quota_wait_seconds(QuotaError("44s")) == 45.0
    assert quota_wait_seconds(QuotaError("2.5s")) == 3.5
    assert quota_wait_seconds(QuotaError(None)) is None  # hết hạn mức không có thời gian chờ
    assert quota_wait_seconds(QuotaError("44s", code=503)) is None
    assert quota_wait_seconds(RuntimeError("lạ")) is None


def test_gemini_waits_out_a_per_minute_quota_then_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr("app.assistant.providers.gemini_provider.time.sleep", slept.append)
    client = FlakyGemini(failures=2, delay="30s")

    reply = GeminiProvider("khoa", client=client).chat(CONVERSATION[:2], [])

    assert reply.text == "Xong." and client.calls == 3 and slept == [31.0, 31.0]


@pytest.mark.parametrize(
    ("delay", "failures"),
    [
        (None, 1),  # không có thời gian chờ ngắn (ví dụ Pro trên gói miễn phí)
        (f"{int(MAX_QUOTA_WAIT_SECONDS) + 60}s", 1),  # chờ quá lâu để giữ một yêu cầu web
        ("5s", 99),  # vẫn hết hạn mức sau mọi lần thử
    ],
)
def test_gemini_gives_up_on_quota_errors_it_cannot_wait_out(
    monkeypatch: pytest.MonkeyPatch, delay: str | None, failures: int
) -> None:
    monkeypatch.setattr("app.assistant.providers.gemini_provider.time.sleep", lambda _s: None)

    with pytest.raises(LLMError) as raised:
        GeminiProvider("khoa", client=FlakyGemini(failures, delay)).chat(CONVERSATION[:2], [])

    assert "429" in str(raised.value)


def test_gemini_errors_empty_and_blocked_replies_become_llm_error_without_leaks() -> None:
    class Quota(Exception):
        code = 429

    with pytest.raises(LLMError) as raised:
        GeminiProvider("khoa", client=FakeGemini(error=Quota("AQ.khoa-bi-mat"))).chat(
            CONVERSATION[:2], [SPEC]
        )
    assert "AQ.khoa" not in str(raised.value) and "429" in str(raised.value)
    with pytest.raises(LLMError):
        GeminiProvider("khoa", client=FakeGemini(None)).chat(CONVERSATION[:2], [SPEC])  # bị chặn
    with pytest.raises(LLMError):
        GeminiProvider("khoa", client=FakeGemini([gem_text("", thought=False)])).chat(
            CONVERSATION[:2], [SPEC]
        )


# --- Chọn nhà cung cấp theo cấu hình -----------------------------------------------------------


def settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": "postgresql+psycopg://x:x@localhost/x",
        "jwt_secret": "x" * 40,
        "llm_provider": "",
        "llm_api_key": "",
        "llm_model": "",
    }
    values.update(overrides)
    return Settings(**values)


def test_anthropic_is_chosen_by_llm_provider() -> None:
    provider = build_provider(settings(llm_provider="anthropic", llm_api_key="khoa"))

    assert isinstance(provider, AnthropicProvider)
    assert provider.model == DEFAULT_MODEL


def test_gemini_is_chosen_by_llm_provider() -> None:
    provider = build_provider(settings(llm_provider="gemini", llm_api_key="khoa"))

    assert isinstance(provider, GeminiProvider)
    assert provider.model == GEMINI_DEFAULT_MODEL


def test_ollama_is_chosen_by_llm_provider() -> None:
    provider = build_provider(settings(llm_provider="ollama", llm_model="qwen2.5:7b"))

    assert isinstance(provider, OllamaProvider)
    assert provider.model == "qwen2.5:7b"


@pytest.mark.parametrize(
    "overrides",
    [
        {},  # chưa chọn nhà cung cấp
        {"llm_provider": "anthropic"},  # thiếu khoá
        {"llm_provider": "gemini"},  # thiếu khoá
        {"llm_provider": "ollama"},  # thiếu mô hình
    ],
)
def test_incomplete_configuration_is_reported_not_guessed(overrides: dict[str, Any]) -> None:
    with pytest.raises(LLMNotConfigured):
        build_provider(settings(**overrides))


def test_unknown_provider_name_is_rejected_by_settings() -> None:
    with pytest.raises(ValueError):
        settings(llm_provider="openai")

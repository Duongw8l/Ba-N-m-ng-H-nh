"""Chọn nhà cung cấp LLM theo biến môi trường LLM_PROVIDER (D-085)."""

from functools import lru_cache

from app.assistant.llm import LLMNotConfigured, LLMProvider
from app.core.config import Settings, get_settings


def build_provider(settings: Settings) -> LLMProvider:
    """Dựng nhà cung cấp theo cấu hình; thiếu thông tin thì ném `LLMNotConfigured`."""
    if settings.llm_provider == "anthropic":
        from app.assistant.providers.anthropic_provider import AnthropicProvider

        api_key = settings.llm_api_key.get_secret_value()
        if not api_key:
            raise LLMNotConfigured("Chưa đặt LLM_API_KEY cho nhà cung cấp anthropic.")
        return AnthropicProvider(api_key, settings.llm_model, float(settings.llm_timeout_seconds))
    if settings.llm_provider == "gemini":
        from app.assistant.providers.gemini_provider import GeminiProvider

        api_key = settings.llm_api_key.get_secret_value()
        if not api_key:
            raise LLMNotConfigured("Chưa đặt LLM_API_KEY cho nhà cung cấp gemini.")
        return GeminiProvider(api_key, settings.llm_model, float(settings.llm_timeout_seconds))
    if settings.llm_provider == "ollama":
        from app.assistant.providers.ollama_provider import OllamaProvider

        if not settings.llm_model:
            raise LLMNotConfigured("Chưa đặt LLM_MODEL cho nhà cung cấp ollama.")
        return OllamaProvider(
            settings.ollama_url, settings.llm_model, float(settings.llm_timeout_seconds)
        )
    raise LLMNotConfigured("Chưa cấu hình LLM_PROVIDER (anthropic, gemini hoặc ollama).")


@lru_cache
def get_llm_provider() -> LLMProvider:
    return build_provider(get_settings())

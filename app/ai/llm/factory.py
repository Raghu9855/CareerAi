"""Dependency injection factory for configured LLM clients."""

from functools import lru_cache

from app.ai.llm.client import LLMClient
from app.ai.llm.mock import MockLLMClient
from app.ai.llm.provider import OpenAICompatibleClient
from app.ai.llm.resilience import ResilientLLMClient
from app.core.config import get_settings


@lru_cache
def get_llm_client() -> LLMClient:
    """Instantiate and wrap configured LLM client based on application environment."""
    settings = get_settings()
    provider = settings.LLM_PROVIDER.lower()

    inner: LLMClient
    if provider == "mock":
        inner = MockLLMClient(model_name=settings.resolved_llm_model)
    elif provider == "ollama":
        inner = OpenAICompatibleClient(
            api_key=settings.LLM_API_KEY or "ollama",
            base_url=settings.resolved_llm_base_url,
            model=settings.resolved_llm_model,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        )
    elif not settings.LLM_API_KEY:
        # Fall back to mock client if API key is not supplied
        inner = MockLLMClient(model_name=settings.resolved_llm_model)
    else:
        inner = OpenAICompatibleClient(
            api_key=settings.LLM_API_KEY,
            base_url=settings.resolved_llm_base_url,
            model=settings.resolved_llm_model,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        )

    return ResilientLLMClient(
        inner_client=inner,
        max_retries=settings.LLM_MAX_RETRIES,
        base_delay=0.3,
        max_delay=3.0,
        enable_cache=True,
    )

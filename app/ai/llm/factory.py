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

    inner: LLMClient
    if settings.LLM_PROVIDER.lower() == "mock" or not settings.LLM_API_KEY:
        inner = MockLLMClient(model_name=settings.LLM_MODEL)
    else:
        inner = OpenAICompatibleClient(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
        )

    return ResilientLLMClient(
        inner_client=inner,
        max_retries=3,
        base_delay=0.3,
        max_delay=3.0,
        enable_cache=True,
    )

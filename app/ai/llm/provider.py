"""Real LLM provider implementation over standard OpenAI-compatible HTTP protocol."""

import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.ai.llm.client import LLMClient, LLMMessage, LLMResponse, LLMUsage
from app.core.config import get_settings
from app.core.errors import AppException, RateLimitError
from app.core.logging import get_logger

logger = get_logger("careerai.ai.llm.provider")


class OpenAICompatibleClient(LLMClient):
    """Production LLM client connecting to OpenAI or compatible gateway."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 30.0,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.LLM_API_KEY
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL
        self.timeout = timeout_seconds

    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Execute chat completion request against HTTP LLM endpoint."""
        if not self.api_key:
            raise AppException(
                message="LLM API key is not configured. Please supply LLM_API_KEY environment variable.",
                status_code=503,
                code="LLM_CONFIG_MISSING",
            )

        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(endpoint, json=payload, headers=headers)

                if response.status_code == 429:
                    raise RateLimitError(
                        message="Provider rate limit exceeded. Backing off.",
                        details={"provider_status": 429},
                    )

                response.raise_for_status()
                data = response.json()

                content = data["choices"][0]["message"]["content"]
                raw_usage = data.get("usage", {})
                usage = LLMUsage(
                    prompt_tokens=raw_usage.get("prompt_tokens", 0),
                    completion_tokens=raw_usage.get("completion_tokens", 0),
                    total_tokens=raw_usage.get("total_tokens", 0),
                )
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                return LLMResponse(
                    content=content,
                    usage=usage,
                    model=self.model,
                    latency_ms=latency_ms,
                    cached=False,
                )
        except httpx.TimeoutException as exc:
            logger.error(f"LLM call timed out after {self.timeout}s: {exc}")
            raise TimeoutError(f"LLM provider request timed out after {self.timeout}s") from exc
        except httpx.HTTPStatusError as exc:
            logger.error(f"LLM HTTP error {exc.response.status_code}: {exc.response.text}")
            raise AppException(
                message=f"LLM provider returned HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
                code="LLM_PROVIDER_ERROR",
            ) from exc

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> AsyncGenerator[str, None]:
        """Stream chunks from provider (falls back to single generate if streaming endpoint unavailable)."""
        resp = await self.generate(messages, temperature=temperature, max_tokens=max_tokens)
        yield resp.content

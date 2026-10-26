"""Ollama LLM provider implementation over native asynchronous HTTP API."""

import json
import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.ai.llm.client import LLMClient, LLMMessage, LLMResponse, LLMUsage
from app.core import config
from app.core.errors import (
    ExternalServiceError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
)
from app.core.logging import get_logger

logger = get_logger("careerai.ai.llm.ollama")


class OllamaClient(LLMClient):
    """Production asynchronous LLM client communicating with a local Ollama server."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        settings = config.get_settings()
        raw_url = base_url or settings.resolved_ollama_base_url
        self.base_url = self._normalize_base_url(raw_url)
        self.model = model or settings.resolved_llm_model
        self.timeout = float(timeout_seconds if timeout_seconds is not None else settings.LLM_TIMEOUT_SECONDS)

    @staticmethod
    def _normalize_base_url(url: str) -> str:
        """Strip trailing slashes and extraneous API prefixes."""
        normalized = url.rstrip("/")
        if normalized.endswith("/v1"):
            normalized = normalized[:-3].rstrip("/")
        if normalized.endswith("/api"):
            normalized = normalized[:-4].rstrip("/")
        return normalized

    def _build_payload(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        response_format: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Construct the Ollama /api/chat request payload."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        # Handle structured JSON formatting
        if response_format:
            if isinstance(response_format, dict):
                if "schema" in response_format:
                    payload["format"] = response_format["schema"]
                else:
                    payload["format"] = "json"
            elif isinstance(response_format, str):
                payload["format"] = response_format
        else:
            # Auto-detect if system instructions explicitly require structured JSON
            first_sys = next((m.content for m in messages if m.role == "system"), "")
            if "Respond ONLY with a valid JSON" in first_sys or "Respond ONLY with valid JSON" in first_sys:
                payload["format"] = "json"

        return payload

    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Execute chat completion request against Ollama /api/chat endpoint."""
        endpoint = f"{self.base_url}/api/chat"
        payload = self._build_payload(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            stream=False,
        )

        # Safe logging: log metadata only, NEVER user resumes, prompts, or documents
        logger.info(
            "Dispatching Ollama chat completion request",
            extra={
                "model": self.model,
                "endpoint": endpoint,
                "message_count": len(messages),
                "format": payload.get("format"),
                "timeout_seconds": self.timeout,
            },
        )

        timeout = httpx.Timeout(self.timeout, connect=10.0)
        start_time = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(endpoint, json=payload)
                self._handle_http_status_errors(response)

                try:
                    data = response.json()
                except Exception as exc:
                    logger.error(f"Failed to parse Ollama JSON response: {exc}")
                    raise ExternalServiceError(
                        message="Ollama returned invalid non-JSON output",
                        details={"provider": "ollama", "status_code": response.status_code},
                    ) from exc

                if not isinstance(data, dict) or "message" not in data or "content" not in data.get("message", {}):
                    logger.error("Malformed Ollama response payload structure missing 'message.content'")
                    raise ExternalServiceError(
                        message="Ollama returned a malformed response missing message content",
                        details={"provider": "ollama", "raw_keys": list(data.keys()) if isinstance(data, dict) else []},
                    )

                content = data["message"]["content"]
                prompt_tokens = int(data.get("prompt_eval_count") or 0)
                completion_tokens = int(data.get("eval_count") or 0)
                usage = LLMUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                )
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                # Safe logging: log metrics only, do NOT log generated content
                logger.info(
                    "Ollama chat completion succeeded",
                    extra={
                        "model": data.get("model", self.model),
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                        "latency_ms": latency_ms,
                    },
                )

                return LLMResponse(
                    content=content,
                    usage=usage,
                    model=data.get("model", self.model),
                    latency_ms=latency_ms,
                    cached=False,
                )

        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            logger.error(f"Cannot connect to Ollama at {self.base_url}: {exc}")
            raise ServiceUnavailableError(
                message=(
                    f"Failed to connect to Ollama server at {self.base_url}. "
                    "Ensure Ollama is running ('ollama serve')."
                ),
                details={"provider": "ollama", "base_url": self.base_url},
            ) from exc

        except httpx.TimeoutException as exc:
            logger.error(f"Ollama request timed out after {self.timeout}s: {exc}")
            raise TimeoutError(f"Ollama request timed out after {self.timeout}s") from exc

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> AsyncGenerator[str, None]:
        """Stream completion tokens asynchronously from Ollama /api/chat."""
        endpoint = f"{self.base_url}/api/chat"
        payload = self._build_payload(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        timeout = httpx.Timeout(self.timeout, connect=10.0)

        try:
            async with (
                httpx.AsyncClient(timeout=timeout) as client,
                client.stream("POST", endpoint, json=payload) as response,
            ):
                self._handle_http_status_errors(response)
                async for line in response.aiter_lines():
                        if not line or not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                            chunk_text = chunk.get("message", {}).get("content", "")
                            if chunk_text:
                                yield chunk_text
                        except Exception as exc:
                            logger.warning(f"Skipping malformed streaming chunk from Ollama: {exc}")
                            continue

        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            logger.error(f"Cannot connect to Ollama stream at {self.base_url}: {exc}")
            raise ServiceUnavailableError(
                message=f"Failed to connect to Ollama server at {self.base_url}",
                details={"provider": "ollama", "base_url": self.base_url},
            ) from exc

        except httpx.TimeoutException as exc:
            logger.error(f"Ollama streaming timed out after {self.timeout}s: {exc}")
            raise TimeoutError(f"Ollama streaming timed out after {self.timeout}s") from exc

    def _handle_http_status_errors(self, response: httpx.Response) -> None:
        """Inspect HTTP response and map failure codes to domain exceptions."""
        if response.status_code == 200:
            return

        detail = ""
        try:
            body = response.json()
            if isinstance(body, dict):
                detail = body.get("error", response.text)
        except Exception:
            detail = response.text

        logger.error(
            f"Ollama HTTP error {response.status_code}: {detail}",
            extra={"status_code": response.status_code, "model": self.model},
        )

        if response.status_code == 404:
            raise NotFoundError(
                message=f"Ollama model '{self.model}' not found on server. Pull it using 'ollama pull {self.model}'.",
                details={"provider": "ollama", "model": self.model, "status_code": 404, "detail": detail},
            )
        if response.status_code == 429:
            raise RateLimitError(
                message="Ollama request rate limit exceeded",
                details={"provider": "ollama", "status_code": 429},
            )
        if response.status_code in (502, 503, 504):
            raise ServiceUnavailableError(
                message=f"Ollama server unavailable (HTTP {response.status_code}): {detail}",
                details={"provider": "ollama", "status_code": response.status_code, "detail": detail},
            )

        raise ExternalServiceError(
            message=f"Ollama provider returned HTTP {response.status_code}: {detail}",
            details={"provider": "ollama", "status_code": response.status_code, "detail": detail},
        )

    async def check_health(self) -> bool:
        """Verify Ollama server connectivity and responsiveness."""
        endpoint = f"{self.base_url}/api/version"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
                res = await client.get(endpoint)
                return res.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """Fetch list of locally installed models on the Ollama server."""
        endpoint = f"{self.base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
                res = await client.get(endpoint)
                if res.status_code == 200:
                    data = res.json()
                    models = data.get("models", [])
                    return [m.get("name", "") for m in models if isinstance(m, dict) and "name" in m]
        except Exception as exc:
            logger.warning(f"Could not retrieve Ollama model list from {endpoint}: {exc}")
        return []

    async def aclose(self) -> None:
        """Asynchronously release resources."""
        return None

    async def close(self) -> None:
        """Alias for aclose for compatibility."""
        return None

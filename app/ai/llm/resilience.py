"""Resilience wrapper providing retries with jitter, in-memory caching, deduplication, and usage metrics."""

import asyncio
import contextlib
import hashlib
import json
import random
import time
from collections.abc import AsyncGenerator
from typing import Any

from app.ai.llm.client import LLMClient, LLMMessage, LLMResponse
from app.core.errors import (
    AppException,
    ExternalServiceError,
    RateLimitError,
    ServiceUnavailableError,
)
from app.core.logging import get_logger

logger = get_logger("careerai.ai.llm.resilience")


class ResilientLLMClient(LLMClient):
    """Decorator providing fault tolerance, retries with backoff + jitter, caching, and deduplication."""

    def __init__(
        self,
        inner_client: LLMClient,
        max_retries: int = 3,
        base_delay: float = 0.2,
        max_delay: float = 3.0,
        enable_cache: bool = True,
    ) -> None:
        self.inner_client = inner_client
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.enable_cache = enable_cache

        # Cache: hash -> (LLMResponse, expiry_timestamp)
        self._cache: dict[str, tuple[LLMResponse, float]] = {}
        # In-flight deduplication: hash -> asyncio.Task / Future
        self._in_flight: dict[str, asyncio.Future[LLMResponse]] = {}
        self._lock = asyncio.Lock()

    def _hash_request(
        self,
        messages: list[LLMMessage],
        temperature: float,
        max_tokens: int,
        response_format: dict[str, Any] | None,
    ) -> str:
        """Create deterministic SHA256 digest of request parameters."""
        payload = {
            "messages": [{"r": m.role, "c": m.content} for m in messages],
            "t": temperature,
            "m": max_tokens,
            "fmt": response_format,
        }
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Execute request with caching, deduplication, and retries with jitter."""
        req_hash = self._hash_request(messages, temperature, max_tokens, response_format)

        # 1. Cache hit check
        if self.enable_cache:
            cached_item = self._cache.get(req_hash)
            if cached_item:
                cached_resp, expiry = cached_item
                if time.time() < expiry:
                    logger.info(f"LLM request cache hit: key={req_hash[:10]}...")
                    return LLMResponse(
                        content=cached_resp.content,
                        usage=cached_resp.usage,
                        model=cached_resp.model,
                        latency_ms=0.5,
                        cached=True,
                    )
                else:
                    self._cache.pop(req_hash, None)

        # 2. In-flight request deduplication
        async with self._lock:
            if req_hash in self._in_flight:
                logger.info(f"Deduplicating in-flight LLM request: key={req_hash[:10]}...")
                future = self._in_flight[req_hash]
                # Release lock while waiting for the in-flight task to complete
                await asyncio.sleep(0)
                return await future

            # Create future for this request
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            self._in_flight[req_hash] = future

        # 3. Execute with retries & jitter
        try:
            response = await self._execute_with_retries(messages, temperature, max_tokens, response_format)

            # Populate cache (default TTL 30 minutes)
            if self.enable_cache:
                self._cache[req_hash] = (response, time.time() + 1800.0)

            future.set_result(response)
            return response
        except Exception as exc:
            if not future.done():
                future.set_exception(exc)
                with contextlib.suppress(Exception):
                    future.exception()
            raise
        finally:
            async with self._lock:
                self._in_flight.pop(req_hash, None)

    async def _execute_with_retries(
        self,
        messages: list[LLMMessage],
        temperature: float,
        max_tokens: int,
        response_format: dict[str, Any] | None,
    ) -> LLMResponse:
        """Execute call with exponential backoff and randomized jitter on transient errors."""
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await self.inner_client.generate(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                )

                # Token & latency metrics logging
                logger.info(
                    "LLM generation succeeded",
                    extra={
                        "model": response.model,
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                        "latency_ms": response.latency_ms,
                    },
                )
                return response

            except RETRYABLE_EXCEPTIONS as exc:
                last_exception = exc
                if attempt >= self.max_retries:
                    logger.error(f"LLM exhausted all {self.max_retries} retries: {exc}")
                    raise

                # Exponential backoff with jitter: delay = min(max_delay, base * 2^attempt) + jitter
                jitter = random.uniform(0.05, 0.25)
                delay = min(self.max_delay, self.base_delay * (2**attempt)) + jitter
                logger.warning(
                    f"LLM call transient failure (attempt {attempt + 1}/{self.max_retries}): {exc}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)

            except Exception as exc:
                # Fatal or non-transient error, don't retry
                logger.error(f"Non-retryable LLM failure: {exc}")
                raise

        if last_exception:
            raise last_exception
        raise AppException(message="Unexpected LLM failure state", status_code=500)

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> AsyncGenerator[str, None]:
        """Delegate streaming to inner client."""
        async for chunk in self.inner_client.generate_stream(messages, temperature=temperature, max_tokens=max_tokens):
            yield chunk


try:
    import httpx

    RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
        RateLimitError,
        TimeoutError,
        ConnectionError,
        ExternalServiceError,
        ServiceUnavailableError,
        httpx.TimeoutException,
        httpx.NetworkError,
        httpx.HTTPStatusError,
    )
except ImportError:
    RETRYABLE_EXCEPTIONS = (
        RateLimitError,
        TimeoutError,
        ConnectionError,
        ExternalServiceError,
        ServiceUnavailableError,
    )

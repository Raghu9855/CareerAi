"""Unit tests for MockLLMClient and ResilientLLMClient resilience mechanisms."""

import asyncio

import pytest

from app.ai.llm.client import LLMMessage
from app.ai.llm.mock import MockLLMClient
from app.ai.llm.resilience import ResilientLLMClient
from app.core.errors import RateLimitError


@pytest.mark.asyncio
async def test_mock_llm_client_generation_and_streaming() -> None:
    """Verify MockLLMClient generates structured output and streams tokens."""
    client = MockLLMClient()
    messages = [
        LLMMessage(role="system", content="You are CareerAI."),
        LLMMessage(role="user", content="Explain analysis fit for Python role."),
    ]
    resp = await client.generate(messages)
    assert resp.content != ""
    assert "summary" in resp.content
    assert resp.usage.total_tokens > 0
    assert resp.cached is False

    # Test streaming
    streamed_chunks = []
    async for chunk in client.generate_stream(messages):
        streamed_chunks.append(chunk)
    assert len(streamed_chunks) > 0
    assert "".join(streamed_chunks).strip() == resp.content.strip()


@pytest.mark.asyncio
async def test_resilient_llm_caching() -> None:
    """Verify ResilientLLMClient caches identical requests and prevents duplicate calls."""
    inner = MockLLMClient()
    resilient = ResilientLLMClient(inner_client=inner, enable_cache=True)

    messages = [LLMMessage(role="user", content="Identical prompt query.")]

    resp1 = await resilient.generate(messages)
    assert resp1.cached is False
    assert inner.call_count == 1

    # Second call with identical payload must hit cache
    resp2 = await resilient.generate(messages)
    assert resp2.cached is True
    assert inner.call_count == 1  # Inner client was NOT called again


@pytest.mark.asyncio
async def test_resilient_llm_in_flight_deduplication() -> None:
    """Verify concurrent identical requests are deduplicated in-flight."""
    inner = MockLLMClient(simulated_latency=0.05)
    resilient = ResilientLLMClient(inner_client=inner, enable_cache=True)

    messages = [LLMMessage(role="user", content="Concurrent identical query.")]

    # Launch two concurrent identical generation requests
    results = await asyncio.gather(
        resilient.generate(messages),
        resilient.generate(messages),
    )
    assert len(results) == 2
    assert inner.call_count == 1  # Deduplicated into a single invocation!


@pytest.mark.asyncio
async def test_resilient_llm_retries_on_rate_limit() -> None:
    """Verify ResilientLLMClient retries with backoff and raises RateLimitError when retries are exhausted."""
    inner = MockLLMClient(simulate_rate_limit=True)
    resilient = ResilientLLMClient(inner_client=inner, max_retries=2, base_delay=0.01, max_delay=0.05)

    messages = [LLMMessage(role="user", content="Rate limited prompt.")]
    with pytest.raises(RateLimitError):
        await resilient.generate(messages)

    # 1 initial attempt + 2 retries = 3 calls
    assert inner.call_count == 3


@pytest.mark.asyncio
async def test_resilient_llm_retries_on_timeout() -> None:
    """Verify ResilientLLMClient retries on simulated timeout."""
    inner = MockLLMClient(simulate_timeout=True)
    resilient = ResilientLLMClient(inner_client=inner, max_retries=2, base_delay=0.01, max_delay=0.05)

    messages = [LLMMessage(role="user", content="Timeout prompt.")]
    with pytest.raises(TimeoutError):
        await resilient.generate(messages)

    assert inner.call_count == 3


@pytest.mark.asyncio
async def test_mock_llm_malformed_json_output() -> None:
    """Verify mock client can simulate malformed JSON payloads."""
    client = MockLLMClient(simulate_malformed_json=True)
    resp = await client.generate([LLMMessage(role="user", content="Malformed test.")])
    assert "Incomplete and malformed" in resp.content

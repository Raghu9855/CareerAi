"""Unit tests for the webhook dispatcher core module."""

import hashlib
import hmac
import json
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.webhook_dispatcher import (
    _MAX_ATTEMPTS,
    build_payload,
    compute_signature,
    dispatch_once,
    max_attempts,
    next_retry_at,
)

# ---------------------------------------------------------------------------
# compute_signature
# ---------------------------------------------------------------------------


def test_compute_signature_format() -> None:
    """Signature must be prefixed with 'sha256='."""
    sig = compute_signature(b"hello", "my-secret")
    assert sig.startswith("sha256=")


def test_compute_signature_correct_hmac() -> None:
    """Computed HMAC must match a reference implementation."""
    payload = b'{"event":"test"}'
    secret = "my-secret-key"
    expected_mac = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert compute_signature(payload, secret) == f"sha256={expected_mac}"


def test_compute_signature_different_secrets_differ() -> None:
    """Different secrets must produce different signatures."""
    payload = b"same payload"
    assert compute_signature(payload, "secret-a") != compute_signature(payload, "secret-b")


def test_compute_signature_different_payloads_differ() -> None:
    """Different payloads must produce different signatures."""
    secret = "same-secret"
    assert compute_signature(b"payload-a", secret) != compute_signature(b"payload-b", secret)


# ---------------------------------------------------------------------------
# build_payload
# ---------------------------------------------------------------------------


def test_build_payload_structure() -> None:
    """Webhook envelope must contain event, delivery_id, timestamp, and data."""
    payload = build_payload("application.created", {"application_id": 42}, delivery_id=7)
    assert payload["event"] == "application.created"
    assert payload["delivery_id"] == 7
    assert payload["data"] == {"application_id": 42}
    assert "timestamp" in payload


def test_build_payload_no_delivery_id() -> None:
    """delivery_id defaults to None when not provided."""
    payload = build_payload("webhook.test", {})
    assert payload["delivery_id"] is None


# ---------------------------------------------------------------------------
# next_retry_at
# ---------------------------------------------------------------------------


def test_next_retry_at_returns_datetime_for_first_attempt() -> None:
    """First retry should return a future datetime."""
    result = next_retry_at(0)
    assert result is not None
    from datetime import datetime

    assert result > datetime.now(UTC)


def test_next_retry_at_returns_none_when_exhausted() -> None:
    """After MAX_ATTEMPTS retries the scheduler should return None."""
    result = next_retry_at(_MAX_ATTEMPTS)
    assert result is None


def test_max_attempts_value() -> None:
    """max_attempts() helper must return the same constant as _MAX_ATTEMPTS."""
    assert max_attempts() == _MAX_ATTEMPTS


# ---------------------------------------------------------------------------
# dispatch_once — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_once_success() -> None:
    """dispatch_once must return (True, status, body) on a 2xx response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "OK"

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.core.webhook_dispatcher.httpx.AsyncClient", return_value=mock_client):
        success, status_code, body = await dispatch_once(
            url="https://example.com/hook",
            secret="test-secret-key",
            payload={"event": "test"},
        )

    assert success is True
    assert status_code == 200
    assert body == "OK"


@pytest.mark.asyncio
async def test_dispatch_once_non_2xx_failure() -> None:
    """dispatch_once must return (False, status, body) on a 4xx/5xx response."""
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.text = "Service Unavailable"

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.core.webhook_dispatcher.httpx.AsyncClient", return_value=mock_client):
        success, status_code, body = await dispatch_once(
            url="https://example.com/hook",
            secret="test-secret-key",
            payload={"event": "test"},
        )

    assert success is False
    assert status_code == 503


@pytest.mark.asyncio
async def test_dispatch_once_timeout() -> None:
    """dispatch_once must return (False, None, error_msg) on timeout."""
    import httpx

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

    with patch("app.core.webhook_dispatcher.httpx.AsyncClient", return_value=mock_client):
        success, status_code, body = await dispatch_once(
            url="https://slow.example.com/hook",
            secret="test-secret-key",
            payload={"event": "test"},
        )

    assert success is False
    assert status_code is None
    assert "timed out" in body.lower() or "timeout" in body.lower()


@pytest.mark.asyncio
async def test_dispatch_once_sets_correct_headers() -> None:
    """dispatch_once must set X-CareerAI-Signature, X-CareerAI-Event, and Content-Type headers."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "OK"
    captured_headers: dict = {}

    async def capture_post(url: str, content: bytes, headers: dict, **kwargs):  # type: ignore[no-untyped-def]
        captured_headers.update(headers)
        return mock_response

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=capture_post)

    test_payload = {"event": "application.created", "data": {}}
    with patch("app.core.webhook_dispatcher.httpx.AsyncClient", return_value=mock_client):
        await dispatch_once(
            url="https://example.com/hook",
            secret="my-signing-secret",
            payload=test_payload,
        )

    assert "X-CareerAI-Signature" in captured_headers
    assert captured_headers["X-CareerAI-Signature"].startswith("sha256=")
    assert captured_headers["X-CareerAI-Event"] == "application.created"
    assert captured_headers["Content-Type"] == "application/json"

    # Verify the signature matches the payload bytes
    payload_bytes = json.dumps(test_payload, default=str).encode()
    expected_sig = compute_signature(payload_bytes, "my-signing-secret")
    assert captured_headers["X-CareerAI-Signature"] == expected_sig

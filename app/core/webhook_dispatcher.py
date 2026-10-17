"""Asynchronous webhook dispatcher: HMAC-SHA256 signing, delivery, retries, and audit logging."""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger("careerai.webhook.dispatcher")

# Delivery configuration
_MAX_ATTEMPTS = 5
_TIMEOUT_SECONDS = 10.0
# Exponential back-off delays in seconds: 30s, 5m, 30m, 2h, 6h
_RETRY_DELAYS_SECONDS = [30, 300, 1800, 7200, 21600]


def compute_signature(payload_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for a raw payload and shared secret.

    The resulting header value is prefixed with ``sha256=`` matching the GitHub
    webhook convention so that receivers can verify authenticity with a single
    constant-time comparison.
    """
    mac = hmac.new(secret.encode(), payload_bytes, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def build_payload(event: str, data: dict[str, Any], delivery_id: int | None = None) -> dict[str, Any]:
    """Build a standardised webhook envelope."""
    return {
        "event": event,
        "delivery_id": delivery_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "data": data,
    }


async def dispatch_once(
    url: str,
    secret: str,
    payload: dict[str, Any],
) -> tuple[bool, int | None, str]:
    """POST a signed webhook payload to the target URL.

    Returns:
        (success, http_status_code, message_or_error)
    """
    payload_bytes = json.dumps(payload, default=str).encode()
    signature = compute_signature(payload_bytes, secret)
    headers = {
        "Content-Type": "application/json",
        "X-CareerAI-Signature": signature,
        "X-CareerAI-Event": payload.get("event", ""),
        "User-Agent": "CareerAI-Webhooks/1.0",
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, follow_redirects=False) as client:
            response = await client.post(url, content=payload_bytes, headers=headers)
            success = 200 <= response.status_code < 300
            body = response.text[:512]
            if success:
                logger.info(
                    f"Webhook delivered successfully: url={url} status={response.status_code}",
                    extra={"event": payload.get("event")},
                )
            else:
                logger.warning(
                    f"Webhook delivery non-2xx: url={url} status={response.status_code}",
                    extra={"event": payload.get("event")},
                )
            return success, response.status_code, body
    except httpx.TimeoutException:
        msg = f"Delivery timed out after {_TIMEOUT_SECONDS}s"
        logger.warning(f"Webhook timeout: url={url} — {msg}")
        return False, None, msg
    except Exception as exc:
        msg = str(exc)[:512]
        logger.error(f"Webhook dispatch error: url={url} — {msg}")
        return False, None, msg


def next_retry_at(attempt_count: int) -> datetime | None:
    """Compute the absolute datetime for the next retry, or None if exhausted."""
    if attempt_count >= _MAX_ATTEMPTS:
        return None
    delay = _RETRY_DELAYS_SECONDS[min(attempt_count, len(_RETRY_DELAYS_SECONDS) - 1)]
    return datetime.now(UTC) + timedelta(seconds=delay)


def max_attempts() -> int:
    """Maximum number of delivery attempts."""
    return _MAX_ATTEMPTS

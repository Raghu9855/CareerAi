"""Rate limiting primitives and FastAPI dependency factories."""

import time
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request

from app.core.errors import RateLimitError
from app.core.logging import get_logger

logger = get_logger("careerai.ratelimit")


class InMemoryRateLimiter:
    """Sliding window in-memory rate limiter tracking timestamps per client key."""

    def __init__(self) -> None:
        self._history: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, max_requests: int, window_seconds: float = 60.0) -> bool:
        """Check if request is allowed within the sliding window."""
        now = time.time()
        cutoff = now - window_seconds

        # Prune outdated timestamps
        valid_timestamps = [t for t in self._history[key] if t > cutoff]
        self._history[key] = valid_timestamps

        if len(valid_timestamps) >= max_requests:
            return False

        self._history[key].append(now)
        return True

    def reset(self) -> None:
        """Clear all rate limit histories (useful for tests)."""
        self._history.clear()


limiter = InMemoryRateLimiter()


def rate_limit(requests_per_minute: int) -> Callable[[Request], Coroutine[Any, Any, None]]:
    """FastAPI dependency factory enforcing a rate limit based on client IP."""

    async def dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        endpoint = request.url.path
        key = f"{client_ip}:{endpoint}"

        if not limiter.is_allowed(key, max_requests=requests_per_minute, window_seconds=60.0):
            logger.warning(
                f"Rate limit exceeded for {key} (limit: {requests_per_minute}/min)",
                extra={"client_ip": client_ip, "endpoint": endpoint},
            )
            raise RateLimitError(
                message=f"Too many requests. Rate limit is {requests_per_minute} requests per minute.",
                details={"limit": requests_per_minute, "window_seconds": 60},
            )

    return dependency

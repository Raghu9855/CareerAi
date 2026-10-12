"""Rate limiting primitives and FastAPI dependency factories with Redis and in-memory backends."""

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


async def is_rate_limited(key: str, max_requests: int, window_seconds: float = 60.0) -> bool:
    """Checks rate limit against Redis cluster if configured, falling back to local memory."""
    from app.core.redis import get_redis_client

    try:
        redis_client = await get_redis_client()
        if redis_client:
            redis_key = f"ratelimit:{key}"
            now = time.time()
            cutoff = now - window_seconds

            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(redis_key, 0, cutoff)
            pipe.zcard(redis_key)
            pipe.zadd(redis_key, {str(now): now})
            pipe.expire(redis_key, int(window_seconds) + 5)
            results = await pipe.execute()

            request_count = results[1]
            return bool(request_count >= max_requests)
    except Exception as exc:
        logger.debug(f"Redis rate limiter failed ({exc}), falling back to memory limiter")

    # In-memory fallback
    return not limiter.is_allowed(key, max_requests=max_requests, window_seconds=window_seconds)


def rate_limit(requests_per_minute: int) -> Callable[[Request], Coroutine[Any, Any, None]]:
    """FastAPI dependency factory enforcing a rate limit based on client IP."""

    async def dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        endpoint = request.url.path
        key = f"{client_ip}:{endpoint}"

        if await is_rate_limited(key, max_requests=requests_per_minute, window_seconds=60.0):
            logger.warning(
                f"Rate limit exceeded for {key} (limit: {requests_per_minute}/min)",
                extra={"client_ip": client_ip, "endpoint": endpoint},
            )
            raise RateLimitError(
                message=f"Too many requests. Rate limit is {requests_per_minute} requests per minute.",
                details={"limit": requests_per_minute, "window_seconds": 60},
            )

    return dependency

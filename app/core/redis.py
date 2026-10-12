"""Redis client connection pool and caching helper with fallback."""

import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("careerai.redis")

_redis_client: aioredis.Redis | None = None


async def get_redis_client() -> aioredis.Redis | None:
    """Provides or initializes the shared async Redis client."""
    global _redis_client
    settings = get_settings()

    if not settings.REDIS_URL:
        return None

    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            # Ping to verify connectivity
            await _redis_client.ping()
            logger.info("Connected successfully to Redis cluster")
        except Exception as exc:
            logger.warning(f"Could not connect to Redis at {settings.REDIS_URL}: {exc}. Fallback to in-memory mode.")
            _redis_client = None

    return _redis_client


class CacheService:
    """Key-value caching service with automatic serialization and graceful fallback."""

    def __init__(self, client: aioredis.Redis | None = None) -> None:
        self.client = client
        self._local_cache: dict[str, tuple[str, float]] = {}

    @classmethod
    async def create(cls) -> "CacheService":
        client = await get_redis_client()
        return cls(client=client)

    async def get(self, key: str) -> Any | None:
        """Retrieve cached object by key."""
        try:
            if self.client:
                raw = await self.client.get(key)
                if raw:
                    return json.loads(raw)
                return None
        except Exception as exc:
            logger.warning(f"Redis get failed for key {key}: {exc}")

        # Local cache fallback
        import time
        if key in self._local_cache:
            val, expiry = self._local_cache[key]
            if time.time() < expiry:
                return json.loads(val)
            del self._local_cache[key]
        return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """Store serialized object with expiration."""
        serialized = json.dumps(value)
        try:
            if self.client:
                await self.client.set(key, serialized, ex=ttl_seconds)
                return True
        except Exception as exc:
            logger.warning(f"Redis set failed for key {key}: {exc}")

        import time
        self._local_cache[key] = (serialized, time.time() + ttl_seconds)
        return True

    async def delete(self, key: str) -> bool:
        """Invalidate key."""
        try:
            if self.client:
                await self.client.delete(key)
        except Exception:
            pass
        self._local_cache.pop(key, None)
        return True

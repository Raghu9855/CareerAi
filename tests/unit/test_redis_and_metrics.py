"""Unit tests for Redis cache service fallback, background worker, and metrics endpoint."""

import pytest
from httpx import AsyncClient

from app.core.redis import CacheService
from app.workers.worker import BackgroundWorker


@pytest.mark.asyncio
async def test_cache_service_in_memory_fallback() -> None:
    """Verify CacheService operates properly when Redis is in fallback mode."""
    cache = CacheService(client=None)

    # Set and get
    await cache.set("test_key", {"data": "candidate_profile"}, ttl_seconds=60)
    result = await cache.get("test_key")
    assert result == {"data": "candidate_profile"}

    # Delete
    await cache.delete("test_key")
    assert await cache.get("test_key") is None


@pytest.mark.asyncio
async def test_worker_job_processing() -> None:
    """Verify background worker processes supported job types without exceptions."""
    worker = BackgroundWorker()

    await worker.process_job({"type": "extract_document", "document_id": 10})
    await worker.process_job({"type": "index_rag_document", "document_id": 10})
    await worker.process_job({"type": "batch_ml_inference", "user_id": 5})
    await worker.process_job({"type": "unknown_job_type"})


@pytest.mark.asyncio
async def test_metrics_endpoint(client: AsyncClient) -> None:
    """Verify /metrics returns healthy memory and process diagnostics."""
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["memory_rss_mb"] > 0
    assert "model_version" in data

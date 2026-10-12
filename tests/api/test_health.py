"""API tests for health, readiness, metadata, and middleware behavior."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_liveness(client: AsyncClient) -> None:
    """Verifies that the /health liveness probe returns 200 OK and expected structure."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "CareerAI"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_readiness(client: AsyncClient) -> None:
    """Verifies that the /ready readiness probe successfully connects to the database."""
    response = await client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "healthy"


@pytest.mark.asyncio
async def test_api_v1_health_mounted(client: AsyncClient) -> None:
    """Verifies that health checks are also mounted under /api/v1."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient) -> None:
    """Verifies that the root path returns API metadata."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "CareerAI"
    assert data["docs"] == "/docs"


@pytest.mark.asyncio
async def test_request_id_header_propagated(client: AsyncClient) -> None:
    """Verifies that X-Request-ID is generated and returned in headers."""
    response = await client.get("/health")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0

    # Custom request ID propagation
    custom_id = "test-custom-request-id-12345"
    response_with_custom = await client.get("/health", headers={"X-Request-ID": custom_id})
    assert response_with_custom.headers["x-request-id"] == custom_id

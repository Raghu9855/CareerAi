"""Unit tests for IdempotencyMiddleware and replay caching."""

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.middleware.idempotency import IdempotencyMiddleware


@pytest.fixture
def test_app() -> Starlette:
    """Creates a minimal Starlette test app wrapped in IdempotencyMiddleware."""
    call_counter = {"count": 0}

    async def create_item(request: Request) -> JSONResponse:
        call_counter["count"] += 1
        return JSONResponse({"item_id": 42, "execution_count": call_counter["count"]}, status_code=201)

    routes = [Route("/items", create_item, methods=["POST"])]
    app = Starlette(routes=routes)
    app.add_middleware(IdempotencyMiddleware)
    return app


@pytest.mark.asyncio
async def test_idempotency_without_header(test_app: Starlette) -> None:
    """Verify request without X-Idempotency-Key executes normally every time."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        r1 = await client.post("/items")
        assert r1.status_code == 201
        assert r1.json()["execution_count"] == 1

        r2 = await client.post("/items")
        assert r2.status_code == 201
        assert r2.json()["execution_count"] == 2


@pytest.mark.asyncio
async def test_idempotency_with_key_replays_cached_response(test_app: Starlette) -> None:
    """Verify repeat request with identical X-Idempotency-Key returns cached response."""
    transport = ASGITransport(app=test_app)
    headers = {"X-Idempotency-Key": "test-unique-key-12345"}

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # First execution
        r1 = await client.post("/items", headers=headers)
        assert r1.status_code == 201
        data1 = r1.json()
        assert data1["item_id"] == 42
        assert "X-Idempotent-Replay" not in r1.headers

        # Replay with same key
        r2 = await client.post("/items", headers=headers)
        assert r2.status_code == 201
        data2 = r2.json()
        assert data2["item_id"] == 42
        assert data2["execution_count"] == data1["execution_count"]  # Handler was NOT re-executed!
        assert r2.headers.get("X-Idempotent-Replay") == "true"

"""API integration tests for webhook endpoint registration, management, and delivery logs."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_and_login(client: AsyncClient, email: str) -> dict:
    """Register a user and return auth headers."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "Webhook Tester"},
    )
    token = reg.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Endpoint Registration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_webhook_endpoint(client: AsyncClient) -> None:
    """Verify a user can register a webhook endpoint."""
    headers = await _register_and_login(client, "wh_register@example.com")

    resp = await client.post(
        "/api/v1/webhooks/endpoints",
        json={
            "url": "https://example.com/hooks/career",
            "secret": "super-secret-key-at-least-16chars",
            "description": "My ATS callback",
            "events": ["application.created", "application.status_changed"],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["url"] == "https://example.com/hooks/career"
    assert data["description"] == "My ATS callback"
    assert "application.created" in data["events"]
    assert data["is_active"] is True
    assert data["failure_count"] == 0
    assert "id" in data


@pytest.mark.asyncio
async def test_register_webhook_wildcard_events(client: AsyncClient) -> None:
    """Verify that subscribing to all events using '*' is accepted."""
    headers = await _register_and_login(client, "wh_wildcard@example.com")

    resp = await client.post(
        "/api/v1/webhooks/endpoints",
        json={
            "url": "https://example.com/hooks/all",
            "secret": "super-secret-key-at-least-16chars",
            "events": ["*"],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["events"] == ["*"]


@pytest.mark.asyncio
async def test_register_webhook_invalid_event(client: AsyncClient) -> None:
    """Verify that subscribing to an unknown event type returns 422."""
    headers = await _register_and_login(client, "wh_invalid_ev@example.com")

    resp = await client.post(
        "/api/v1/webhooks/endpoints",
        json={
            "url": "https://example.com/hooks/bad",
            "secret": "super-secret-key-at-least-16chars",
            "events": ["totally.fake.event"],
        },
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_duplicate_url_conflict(client: AsyncClient) -> None:
    """Verify that registering the same URL twice returns 409."""
    headers = await _register_and_login(client, "wh_dup@example.com")
    payload = {
        "url": "https://unique.example.com/hook",
        "secret": "super-secret-key-at-least-16chars",
    }
    await client.post("/api/v1/webhooks/endpoints", json=payload, headers=headers)
    dup_resp = await client.post("/api/v1/webhooks/endpoints", json=payload, headers=headers)
    assert dup_resp.status_code == 409


# ---------------------------------------------------------------------------
# List / Get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_webhook_endpoints(client: AsyncClient) -> None:
    """Verify that a user can list their webhook endpoints."""
    headers = await _register_and_login(client, "wh_list@example.com")

    for i in range(3):
        await client.post(
            "/api/v1/webhooks/endpoints",
            json={
                "url": f"https://example.com/hooks/{i}",
                "secret": "super-secret-key-at-least-16chars",
            },
            headers=headers,
        )

    resp = await client.get("/api/v1/webhooks/endpoints", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_get_webhook_endpoint(client: AsyncClient) -> None:
    """Verify that a user can fetch a single endpoint by ID."""
    headers = await _register_and_login(client, "wh_get@example.com")

    create_resp = await client.post(
        "/api/v1/webhooks/endpoints",
        json={"url": "https://example.com/single", "secret": "super-secret-key-at-least-16chars"},
        headers=headers,
    )
    endpoint_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/webhooks/endpoints/{endpoint_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == endpoint_id


@pytest.mark.asyncio
async def test_get_webhook_endpoint_cross_user_isolation(client: AsyncClient) -> None:
    """Verify that User B cannot access User A's webhook endpoint."""
    headers_a = await _register_and_login(client, "wh_iso_a@example.com")
    headers_b = await _register_and_login(client, "wh_iso_b@example.com")

    create_resp = await client.post(
        "/api/v1/webhooks/endpoints",
        json={"url": "https://example.com/secret-hook", "secret": "super-secret-key-at-least-16chars"},
        headers=headers_a,
    )
    endpoint_id = create_resp.json()["id"]

    # User B tries to access User A's endpoint
    resp_b = await client.get(f"/api/v1/webhooks/endpoints/{endpoint_id}", headers=headers_b)
    assert resp_b.status_code == 404


# ---------------------------------------------------------------------------
# Update / Delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_webhook_endpoint(client: AsyncClient) -> None:
    """Verify PATCH updates description and active state."""
    headers = await _register_and_login(client, "wh_update@example.com")

    create_resp = await client.post(
        "/api/v1/webhooks/endpoints",
        json={"url": "https://example.com/update-me", "secret": "super-secret-key-at-least-16chars"},
        headers=headers,
    )
    endpoint_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/v1/webhooks/endpoints/{endpoint_id}",
        json={"description": "Updated label", "is_active": False},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["description"] == "Updated label"
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_delete_webhook_endpoint(client: AsyncClient) -> None:
    """Verify that deleting an endpoint removes it from the list."""
    headers = await _register_and_login(client, "wh_delete@example.com")

    create_resp = await client.post(
        "/api/v1/webhooks/endpoints",
        json={"url": "https://example.com/delete-me", "secret": "super-secret-key-at-least-16chars"},
        headers=headers,
    )
    endpoint_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/webhooks/endpoints/{endpoint_id}", headers=headers)
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/webhooks/endpoints/{endpoint_id}", headers=headers)
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Test Ping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_test_ping_success(client: AsyncClient) -> None:
    """Verify test ping returns delivery record with success when mock delivers successfully."""
    headers = await _register_and_login(client, "wh_ping_ok@example.com")

    create_resp = await client.post(
        "/api/v1/webhooks/endpoints",
        json={"url": "https://example.com/ping-ok", "secret": "super-secret-key-at-least-16chars"},
        headers=headers,
    )
    endpoint_id = create_resp.json()["id"]

    with patch(
        "app.services.webhook_service.dispatch_once",
        new=AsyncMock(return_value=(True, 200, "OK")),
    ):
        resp = await client.post(f"/api/v1/webhooks/endpoints/{endpoint_id}/test", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["http_status_code"] == 200
    assert data["endpoint_id"] == endpoint_id


@pytest.mark.asyncio
async def test_webhook_test_ping_failure(client: AsyncClient) -> None:
    """Verify test ping reflects failure when the endpoint is unreachable."""
    headers = await _register_and_login(client, "wh_ping_fail@example.com")

    create_resp = await client.post(
        "/api/v1/webhooks/endpoints",
        json={"url": "https://example.com/ping-fail", "secret": "super-secret-key-at-least-16chars"},
        headers=headers,
    )
    endpoint_id = create_resp.json()["id"]

    with patch(
        "app.services.webhook_service.dispatch_once",
        new=AsyncMock(return_value=(False, 503, "Service Unavailable")),
    ):
        resp = await client.post(f"/api/v1/webhooks/endpoints/{endpoint_id}/test", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["http_status_code"] == 503


# ---------------------------------------------------------------------------
# Delivery Logs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_delivery_logs(client: AsyncClient) -> None:
    """Verify that delivery logs are created and retrievable after a test ping."""
    headers = await _register_and_login(client, "wh_logs@example.com")

    create_resp = await client.post(
        "/api/v1/webhooks/endpoints",
        json={"url": "https://example.com/logs-test", "secret": "super-secret-key-at-least-16chars"},
        headers=headers,
    )
    endpoint_id = create_resp.json()["id"]

    with patch(
        "app.services.webhook_service.dispatch_once",
        new=AsyncMock(return_value=(True, 200, "OK")),
    ):
        await client.post(f"/api/v1/webhooks/endpoints/{endpoint_id}/test", headers=headers)

    logs_resp = await client.get(f"/api/v1/webhooks/endpoints/{endpoint_id}/deliveries", headers=headers)
    assert logs_resp.status_code == 200
    logs = logs_resp.json()
    assert len(logs) >= 1
    assert logs[0]["event"] == "webhook.test"
    assert logs[0]["status"] == "success"


@pytest.mark.asyncio
async def test_delivery_logs_cross_user_isolation(client: AsyncClient) -> None:
    """Verify User B cannot retrieve delivery logs for User A's endpoint."""
    headers_a = await _register_and_login(client, "wh_log_iso_a@example.com")
    headers_b = await _register_and_login(client, "wh_log_iso_b@example.com")

    create_resp = await client.post(
        "/api/v1/webhooks/endpoints",
        json={"url": "https://example.com/log-iso", "secret": "super-secret-key-at-least-16chars"},
        headers=headers_a,
    )
    endpoint_id = create_resp.json()["id"]

    resp_b = await client.get(f"/api/v1/webhooks/endpoints/{endpoint_id}/deliveries", headers=headers_b)
    assert resp_b.status_code == 404

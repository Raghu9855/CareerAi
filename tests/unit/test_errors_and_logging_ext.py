"""Extensive tests for error handlers, validation errors, and health failure states."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from pydantic import BaseModel

from app.core.errors import (
    ConflictError,
    ExternalServiceError,
    ForbiddenError,
    RateLimitError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationError,
)
from app.db.base import SoftDeleteMixin, TimestampMixin


class DummyModel(TimestampMixin, SoftDeleteMixin):
    pass


def test_exception_classes_attributes() -> None:
    """Tests all domain exception classes instantiate with correct codes and statuses."""
    unauth = UnauthorizedError()
    assert unauth.status_code == 401
    assert unauth.code == "UNAUTHORIZED"

    forbidden = ForbiddenError()
    assert forbidden.status_code == 403
    assert forbidden.code == "FORBIDDEN"

    conflict = ConflictError()
    assert conflict.status_code == 409
    assert conflict.code == "CONFLICT"

    val_err = ValidationError()
    assert val_err.status_code == 422
    assert val_err.code == "VALIDATION_ERROR"

    rate_err = RateLimitError()
    assert rate_err.status_code == 429
    assert rate_err.code == "RATE_LIMIT_EXCEEDED"

    svc_err = ServiceUnavailableError()
    assert svc_err.status_code == 503
    assert svc_err.code == "SERVICE_UNAVAILABLE"

    ext_err = ExternalServiceError()
    assert ext_err.status_code == 502
    assert ext_err.code == "EXTERNAL_SERVICE_ERROR"


def test_soft_delete_mixin() -> None:
    """Verifies that SoftDeleteMixin updates is_deleted and deleted_at."""
    obj = DummyModel()
    obj.is_deleted = False
    obj.deleted_at = None
    obj.soft_delete()
    assert obj.is_deleted is True
    assert obj.deleted_at is not None


@pytest.mark.asyncio
async def test_ready_endpoint_db_failure(client: AsyncClient) -> None:
    """Verifies that /ready returns 503 when check_db_connection returns False."""
    with patch("app.api.v1.routes.health.check_db_connection", return_value=False):
        response = await client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"] == "unhealthy"


@pytest.mark.asyncio
async def test_custom_exception_handling_via_route() -> None:
    """Verifies that raising an AppException in a route results in standard error JSON."""
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()

    @app.get("/test-custom-error")
    async def trigger_custom_error() -> None:
        raise ConflictError("Duplicate resource key", details={"resource": "user"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/test-custom-error")
        assert response.status_code == 409
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "CONFLICT"
        assert data["error"]["message"] == "Duplicate resource key"
        assert data["error"]["details"]["resource"] == "user"


@pytest.mark.asyncio
async def test_validation_error_handling_via_route() -> None:
    """Verifies that Pydantic validation failures trigger validation_exception_handler."""
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()

    class SamplePayload(BaseModel):
        username: str
        age: int

    @app.post("/test-validation")
    async def trigger_validation(payload: SamplePayload) -> dict[str, str]:
        return {"status": "ok"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/test-validation", json={"username": "alex", "age": "not-an-int"})
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "validation_errors" in data["error"]["details"]

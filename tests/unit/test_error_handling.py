"""Unit tests for global exception handlers and unified error envelopes."""

from unittest.mock import MagicMock

import pytest
from fastapi.exceptions import RequestValidationError

from app.core.errors import (
    NotFoundError,
    app_exception_handler,
    create_error_response,
    unhandled_exception_handler,
    validation_exception_handler,
)


def test_create_error_response_envelope() -> None:
    """Verify standard error JSON envelope structure."""
    resp = create_error_response(
        status_code=400,
        code="BAD_REQUEST",
        message="Bad input provided",
        details={"field": "username"},
        request_id="req-abc-123",
    )
    assert resp.status_code == 400
    import json
    data = json.loads(resp.body)
    assert data["success"] is False
    assert data["request_id"] == "req-abc-123"
    assert data["error"]["code"] == "BAD_REQUEST"
    assert data["error"]["message"] == "Bad input provided"
    assert data["error"]["details"]["field"] == "username"


@pytest.mark.asyncio
async def test_app_exception_handler() -> None:
    """Verify domain exception mapping to JSONResponse."""
    req = MagicMock()
    exc = NotFoundError(message="Document with id 42 not found", details={"id": 42})
    resp = await app_exception_handler(req, exc)
    assert resp.status_code == 404
    import json
    data = json.loads(resp.body)
    assert data["error"]["code"] == "NOT_FOUND"
    assert data["error"]["details"]["id"] == 42


@pytest.mark.asyncio
async def test_validation_exception_handler() -> None:
    """Verify Pydantic RequestValidationError formatting."""
    req = MagicMock()
    err_dict = [{"loc": ("body", "email"), "msg": "value is not a valid email address", "type": "value_error"}]
    exc = RequestValidationError(errors=err_dict)
    resp = await validation_exception_handler(req, exc)
    assert resp.status_code == 422
    import json
    data = json.loads(resp.body)
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert len(data["error"]["details"]["validation_errors"]) == 1
    assert data["error"]["details"]["validation_errors"][0]["field"] == "body -> email"


@pytest.mark.asyncio
async def test_unhandled_exception_handler() -> None:
    """Verify unhandled Exception generates 500 without leaking stack traces."""
    req = MagicMock()
    req.method = "POST"
    req.url.path = "/api/v1/jobs"
    exc = RuntimeError("Database socket dropped unexpectedly")
    resp = await unhandled_exception_handler(req, exc)
    assert resp.status_code == 500
    import json
    data = json.loads(resp.body)
    assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "Database socket dropped" not in data["error"]["message"]

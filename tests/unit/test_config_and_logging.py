"""Unit tests for configuration loading, error responses, and logging sanitization."""

from app.core.config import get_settings
from app.core.errors import NotFoundError, create_error_response
from app.core.logging import sanitize_payload


def test_settings_defaults() -> None:
    """Verifies that default settings load with expected values."""
    settings = get_settings()
    assert settings.APP_NAME == "CareerAI"
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0


def test_sensitive_keys_sanitized() -> None:
    """Verifies that passwords, tokens, and secrets are sanitized from logs."""
    raw_data = {
        "username": "alex",
        "password": "SuperSecretPassword123!",
        "access_token": "jwt.secret.token",
        "nested": {
            "api_key": "sk-1234567890",
            "normal_value": 42,
        },
    }

    sanitized = sanitize_payload(raw_data)
    assert sanitized["username"] == "alex"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["nested"]["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["normal_value"] == 42


def test_custom_error_response_format() -> None:
    """Verifies standard unified JSON error response structure."""
    response = create_error_response(
        status_code=404,
        code="NOT_FOUND",
        message="Item not found",
        details={"item_id": 99},
        request_id="req-abc-123",
    )
    assert response.status_code == 404
    import json

    data = json.loads(response.body)
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"
    assert data["error"]["message"] == "Item not found"
    assert data["error"]["details"]["item_id"] == 99
    assert data["request_id"] == "req-abc-123"


def test_not_found_exception() -> None:
    """Verifies NotFoundError attributes."""
    exc = NotFoundError("User not found", details={"user_id": 1})
    assert exc.status_code == 404
    assert exc.code == "NOT_FOUND"
    assert exc.message == "User not found"
    assert exc.details == {"user_id": 1}

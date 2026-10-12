"""Tests for JSONFormatter and logging setup."""

import json
import logging

from app.core.logging import JSONFormatter, request_id_ctx, setup_logging


def test_json_formatter_with_request_id() -> None:
    """Verifies that JSONFormatter outputs valid JSON containing request_id."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test log message",
        args=(),
        exc_info=None,
    )
    token = request_id_ctx.set("req-test-999")
    try:
        formatted = formatter.format(record)
        data = json.loads(formatted)
        assert data["level"] == "INFO"
        assert data["message"] == "Test log message"
        assert data["request_id"] == "req-test-999"
        assert "timestamp" in data
    finally:
        request_id_ctx.reset(token)


def test_setup_logging_runs() -> None:
    """Verifies that setup_logging runs without exception and configures root logger."""
    setup_logging("DEBUG")
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG
    assert len(root_logger.handlers) > 0

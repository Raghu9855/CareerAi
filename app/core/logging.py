"""Structured JSON logging configuration for CareerAI."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Context variable to store the current request ID across async tasks
request_id_ctx: ContextVar[str | None] = ContextVar("request_id_ctx", default=None)

# Sensitive field keys to redact from logs
SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "authorization",
    "api_key",
    "secret_key",
    "content",
    "file_bytes",
    "document_content",
}


def sanitize_payload(payload: Any) -> Any:
    """Recursively redacts sensitive keys from log payload dicts."""
    if isinstance(payload, dict):
        sanitized = {}
        for key, value in payload.items():
            if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, (dict, list)):
                sanitized[key] = sanitize_payload(value)
            else:
                sanitized[key] = value
        return sanitized
    elif isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    return payload


class JSONFormatter(logging.Formatter):
    """Custom logging formatter that outputs logs as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get() or getattr(record, "request_id", None),
        }

        # Include extra attributes passed to the logger
        extra_data = getattr(record, "extra", None)
        if isinstance(extra_data, dict):
            log_entry["extra"] = sanitize_payload(extra_data)

        # Include exception tracebacks if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure the root logger to use JSON formatting."""
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Remove any existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Quiet overly chatty third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("aiomysql").setLevel(logging.WARNING)
    logging.getLogger("asyncmy").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance with the given name."""
    return logging.getLogger(name)

"""Application exception hierarchy and unified error schemas."""

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger, request_id_ctx

logger = get_logger(__name__)


class AppException(Exception):
    """Base exception for all domain and operational application errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppException):
    """Resource was not found."""

    def __init__(self, message: str = "Resource not found", details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class UnauthorizedError(AppException):
    """Authentication failed or credentials are missing/invalid."""

    def __init__(self, message: str = "Authentication required", details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class ForbiddenError(AppException):
    """Authenticated user lacks permission to access resource."""

    def __init__(self, message: str = "Access forbidden", details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ConflictError(AppException):
    """Resource state conflict, e.g. duplicate email, unique constraint."""

    def __init__(self, message: str = "Resource conflict", details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class ValidationError(AppException):
    """Domain validation error."""

    def __init__(self, message: str = "Validation failed", details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details=details,
        )


class RateLimitError(AppException):
    """Client exceeded rate limit."""

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please try again later.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )


class ServiceUnavailableError(AppException):
    """An internal service or dependency is currently unavailable."""

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="SERVICE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


class ExternalServiceError(AppException):
    """Failure communicating with an external third-party service."""

    def __init__(self, message: str = "External service error", details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="EXTERNAL_SERVICE_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details,
        )


def create_error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    """Build a standard JSON error response."""
    current_req_id = request_id or request_id_ctx.get()
    content = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
        "request_id": current_req_id,
    }
    return JSONResponse(status_code=status_code, content=content)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handler for all domain AppException instances."""
    logger.warning(
        f"Domain exception: {exc.code} - {exc.message}",
        extra={"details": exc.details, "status_code": exc.status_code},
    )
    return create_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler for FastAPI Pydantic request validation errors."""
    errors = exc.errors()
    simplified_errors = [
        {
            "field": " -> ".join(str(loc) for loc in err.get("loc", [])),
            "message": err.get("msg"),
            "type": err.get("type"),
        }
        for err in errors
    ]
    return create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="VALIDATION_ERROR",
        message="Invalid request payload or query parameters",
        details={"validation_errors": simplified_errors},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for unexpected unhandled 500 exceptions."""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}", exc_info=True)
    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected internal server error occurred",
    )

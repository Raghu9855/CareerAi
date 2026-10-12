"""HTTP access logging middleware with latency tracking."""

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger("careerai.access")


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Logs incoming HTTP requests, response status codes, and execution duration in ms."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Don't log spammy health check routes in detailed access logs if desired
        is_health = request.url.path in ("/health", "/ready")
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        request_id = getattr(request.state, "request_id", None)

        if not is_health:
            logger.info(
                f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "request_id": request_id,
                    "client_ip": request.client.host if request.client else None,
                },
            )

        return response

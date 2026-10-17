"""Idempotency middleware ensuring safe, duplicate-free request execution."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging import get_logger

logger = get_logger("careerai.idempotency")

# In-memory store for development/testing when Redis is not running
_in_memory_idempotency: dict[str, dict] = {}


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Middleware inspecting X-Idempotency-Key header on mutating HTTP methods.
    Prevents duplicate submissions, payments, applications, and analyses.
    """

    IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in self.IDEMPOTENT_METHODS:
            return await call_next(request)

        idempotency_key = request.headers.get("x-idempotency-key")
        if not idempotency_key:
            return await call_next(request)

        storage_key = f"idempotency:{idempotency_key}"

        # 1. Check if key is already cached
        existing = _in_memory_idempotency.get(storage_key)
        if existing:
            status = existing.get("status")
            if status == "IN_PROGRESS":
                return JSONResponse(
                    status_code=409,
                    content={
                        "success": False,
                        "error": {
                            "code": "CONCURRENT_REQUEST",
                            "message": (
                                "A request with this idempotency key is currently processing. Please retry shortly."
                            ),
                        },
                    },
                )
            elif status == "COMPLETED":
                logger.info(f"Idempotency cache HIT for key: {idempotency_key}")
                headers = dict(existing.get("headers", {}))
                headers["X-Idempotent-Replay"] = "true"
                return Response(
                    content=existing.get("body", b""),
                    status_code=existing.get("status_code", 200),
                    headers=headers,
                    media_type=existing.get("media_type", "application/json"),
                )

        # 2. Mark request IN_PROGRESS
        _in_memory_idempotency[storage_key] = {"status": "IN_PROGRESS"}

        try:
            response = await call_next(request)

            if 200 <= response.status_code < 300:
                body_iterator = getattr(response, "body_iterator", None)
                if body_iterator is not None:
                    response_body = [section async for section in body_iterator]
                    full_body = b"".join(response_body)
                else:
                    full_body = getattr(response, "body", b"")

                _in_memory_idempotency[storage_key] = {
                    "status": "COMPLETED",
                    "status_code": response.status_code,
                    "body": full_body,
                    "media_type": response.media_type,
                    "headers": {
                        k: v for k, v in response.headers.items() if k.lower() in ("content-type", "content-length")
                    },
                }

                # Return fresh response with the reconstructed body
                return Response(
                    content=full_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )
            else:
                # Do not cache error responses
                _in_memory_idempotency.pop(storage_key, None)
                return response

        except Exception:
            _in_memory_idempotency.pop(storage_key, None)
            raise

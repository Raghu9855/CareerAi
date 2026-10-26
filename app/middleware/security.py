"""Security headers middleware enforcing OWASP defensive HTTP headers."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects defensive HTTP security headers into all responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Hugging Face Spaces embeds apps inside an iframe on huggingface.co.
        # Allow frame-ancestors when hosted on hf.space; otherwise enforce strict DENY.
        host = request.headers.get("host", "") + request.headers.get("x-forwarded-host", "")
        if "hf.space" in host or "huggingface" in host:
            response.headers["Content-Security-Policy"] = "frame-ancestors 'self' https://huggingface.co https://*.huggingface.co;"
        else:
            response.headers["X-Frame-Options"] = "DENY"

        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

"""CareerAI FastAPI application entry point and lifespan configuration."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import health
from app.core.config import get_settings
from app.core.errors import (
    AppException,
    app_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import get_logger, setup_logging
from app.db.session import close_db_connections, get_engine
from app.middleware.access_log import AccessLogMiddleware
from app.middleware.idempotency import IdempotencyMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.security import SecurityHeadersMiddleware

logger = get_logger("careerai.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and graceful shutdown lifecycles."""
    settings = get_settings()
    setup_logging(log_level="DEBUG" if settings.APP_DEBUG else "INFO")
    logger.info(
        f"Starting {settings.APP_NAME} in [{settings.APP_ENV}] mode",
        extra={"environment": settings.APP_ENV, "version": "0.1.0"},
    )

    # Initialize database engine
    get_engine()

    # Preload ML model artifact once at startup
    from app.ml.loader import ModelLoader

    model_loader = ModelLoader.get_instance()
    logger.info(f"ML Model loaded: version={model_loader.model_version}, fallback={model_loader.is_fallback}")

    yield

    # Graceful shutdown
    logger.info(f"Shutting down {settings.APP_NAME}...")
    await close_db_connections()
    logger.info("Database connection pools closed.")


def create_app() -> FastAPI:
    """Factory function to build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="CareerAI API",
        description=(
            "AI-Powered Job Intelligence & Fit Analysis Platform Backend. "
            "Provides profile management, resume parsing, ML compatibility scoring, "
            "LLM interview-prep explanations, and RAG document intelligence."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Cross-Origin Resource Sharing (CORS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom Middlewares (order: outermost to innermost)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RequestIdMiddleware)

    # Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Mount Health Check at root
    app.include_router(health.router)

    # Mount versioned API routes under /api/v1
    from app.api.v1.routes import api_v1_router

    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    # Mount Interactive Web UI
    import os

    from starlette.requests import Request
    from starlette.responses import FileResponse, RedirectResponse
    from starlette.staticfiles import StaticFiles

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        # Mount /ui for interactive web dashboard
        app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")

        # Mount /static, /css, and /js so assets resolve whether accessed via /, /ui/, or /static/
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        css_dir = os.path.join(static_dir, "css")
        if os.path.exists(css_dir):
            app.mount("/css", StaticFiles(directory=css_dir), name="css")

        js_dir = os.path.join(static_dir, "js")
        if os.path.exists(js_dir):
            app.mount("/js", StaticFiles(directory=js_dir), name="js")

        @app.get("/app", include_in_schema=False)
        @app.get("/resume-ready", include_in_schema=False)
        async def ui_redirect() -> RedirectResponse:
            return RedirectResponse(url="/ui/")

    @app.get("/", tags=["Root"])
    async def root_info(request: Request) -> Any:
        """Root endpoint: serves interactive UI for browser requests, JSON for API clients."""
        accept = request.headers.get("accept", "")
        index_file = os.path.join(static_dir, "index.html")
        if "text/html" in accept and os.path.exists(index_file):
            return RedirectResponse(url="/ui/")

        return {
            "name": settings.APP_NAME,
            "version": "0.1.0",
            "ui": "/ui/",
            "docs": "/docs",
            "health": "/health",
            "api_v1": settings.API_V1_PREFIX,
        }

    return app


app = create_app()

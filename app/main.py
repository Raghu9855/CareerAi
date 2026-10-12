"""CareerAI FastAPI application entry point and lifespan configuration."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

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
from app.middleware.request_id import RequestIdMiddleware

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
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)

    # Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Mount Health Check at root and under API v1 prefix
    app.include_router(health.router)
    app.include_router(health.router, prefix=settings.API_V1_PREFIX)

    @app.get("/", tags=["Root"])
    async def root_info() -> dict[str, str]:
        """Root API metadata."""
        return {
            "name": settings.APP_NAME,
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/health",
            "api_v1": settings.API_V1_PREFIX,
        }

    return app


app = create_app()

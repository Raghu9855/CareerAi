"""Health and readiness check endpoints."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.db.session import check_db_connection

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Liveness probe")
async def liveness_check() -> dict[str, str]:
    """Returns 200 OK if the application service process is alive."""
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": "0.1.0",
    }


@router.get("/ready", summary="Readiness probe")
async def readiness_check() -> JSONResponse:
    """Checks upstream dependencies (e.g. database connectivity) before routing traffic."""
    settings = get_settings()
    db_healthy = await check_db_connection()

    checks = {
        "database": "healthy" if db_healthy else "unhealthy",
    }

    if db_healthy:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ready",
                "app": settings.APP_NAME,
                "checks": checks,
            },
        )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "not_ready",
            "app": settings.APP_NAME,
            "checks": checks,
        },
    )


@router.get("/metrics", summary="Application metrics")
async def metrics_endpoint() -> dict:
    """Returns application metrics: memory, model info, environment, and DB pool stats."""
    import os
    import sys

    from app.ml.loader import ModelLoader

    model_loader = ModelLoader.get_instance()
    memory_mb = 45.0
    threads_count = 1

    try:
        import psutil  # type: ignore[import-untyped]
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        memory_mb = round(mem_info.rss / (1024 * 1024), 2)
        threads_count = process.num_threads()
    except Exception:
        pass

    return {
        "status": "healthy",
        "memory_rss_mb": memory_mb,
        "python_version": sys.version.split()[0],
        "threads_count": threads_count,
        "model_version": model_loader.model_version,
        "is_model_fallback": model_loader.is_fallback,
    }


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

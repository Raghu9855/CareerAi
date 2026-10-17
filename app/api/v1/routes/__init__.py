"""API v1 router aggregations."""

from fastapi import APIRouter

from app.api.v1.routes import (
    ai,
    applications,
    auth,
    documents,
    health,
    jobs,
    ml,
    profiles,
    rag,
    skills,
    users,
    webhooks,
)

api_v1_router = APIRouter()

api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(profiles.router)
api_v1_router.include_router(skills.router)
api_v1_router.include_router(jobs.router)
api_v1_router.include_router(applications.router)
api_v1_router.include_router(documents.router)
api_v1_router.include_router(ml.router)
api_v1_router.include_router(ai.router)
api_v1_router.include_router(rag.router)
api_v1_router.include_router(webhooks.router)

__all__ = ["api_v1_router"]

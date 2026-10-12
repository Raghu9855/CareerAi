"""API v1 router aggregations."""

from fastapi import APIRouter

from app.api.v1.routes import applications, auth, health, jobs, profiles, skills, users

api_v1_router = APIRouter()

api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(profiles.router)
api_v1_router.include_router(skills.router)
api_v1_router.include_router(jobs.router)
api_v1_router.include_router(applications.router)

__all__ = ["api_v1_router"]

"""Reusable FastAPI dependency providers for database sessions and services."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.application_service import ApplicationService
from app.services.job_service import JobService
from app.services.profile_service import ProfileService
from app.services.skill_service import SkillService
from app.services.user_service import UserService


async def get_db_session(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[AsyncSession, None]:
    """Provides an active database session for route handlers."""
    yield session


def get_user_service(session: AsyncSession = Depends(get_db)) -> UserService:
    """Dependency that provides UserService."""
    return UserService(session)


def get_profile_service(session: AsyncSession = Depends(get_db)) -> ProfileService:
    """Dependency that provides ProfileService."""
    return ProfileService(session)


def get_skill_service(session: AsyncSession = Depends(get_db)) -> SkillService:
    """Dependency that provides SkillService."""
    return SkillService(session)


def get_job_service(session: AsyncSession = Depends(get_db)) -> JobService:
    """Dependency that provides JobService."""
    return JobService(session)


def get_application_service(session: AsyncSession = Depends(get_db)) -> ApplicationService:
    """Dependency that provides ApplicationService."""
    return ApplicationService(session)

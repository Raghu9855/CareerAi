"""Reusable FastAPI dependency providers for database sessions, services, and authentication."""

from collections.abc import AsyncGenerator, Callable

import jwt
from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.user_repo import UserRepository
from app.services.application_service import ApplicationService
from app.services.auth_service import AuthService
from app.services.job_service import JobService
from app.services.profile_service import ProfileService
from app.services.skill_service import SkillService
from app.services.user_service import UserService

# HTTP Bearer authentication scheme
http_bearer = HTTPBearer(auto_error=False)


async def get_db_session(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[AsyncSession, None]:
    """Provides an active database session for route handlers."""
    yield session


def get_auth_service(session: AsyncSession = Depends(get_db)) -> AuthService:
    """Provides AuthService instance."""
    return AuthService(session)


def get_user_service(session: AsyncSession = Depends(get_db)) -> UserService:
    """Provides UserService instance."""
    return UserService(session)


def get_profile_service(session: AsyncSession = Depends(get_db)) -> ProfileService:
    """Provides ProfileService instance."""
    return ProfileService(session)


def get_skill_service(session: AsyncSession = Depends(get_db)) -> SkillService:
    """Provides SkillService instance."""
    return SkillService(session)


def get_job_service(session: AsyncSession = Depends(get_db)) -> JobService:
    """Provides JobService instance."""
    return JobService(session)


def get_application_service(session: AsyncSession = Depends(get_db)) -> ApplicationService:
    """Provides ApplicationService instance."""
    return ApplicationService(session)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Extracts and verifies the JWT access token, returning the authenticated user."""
    if not credentials or not credentials.credentials:
        raise UnauthorizedError(message="Authentication credentials required")

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except jwt.PyJWTError as exc:
        raise UnauthorizedError(message="Invalid or expired access token") from exc

    if payload.get("type") != "access":
        raise UnauthorizedError(message="Invalid token type: expected access token")

    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedError(message="Malformed access token payload")

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(int(sub))
    if not user:
        raise UnauthorizedError(message="User associated with token no longer exists")

    if not user.is_active:
        raise UnauthorizedError(message="User account is deactivated")

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensures authenticated user is active."""
    return current_user


def require_role(*roles: UserRole) -> Callable[[User], User]:
    """Dependency factory restricting endpoint access to specific user roles."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise ForbiddenError(
                message=f"Access forbidden: role '{current_user.role}' lacks required permissions",
                details={"required_roles": [r.value for r in roles], "user_role": current_user.role.value},
            )
        return current_user

    return role_checker


async def get_requesting_user_or_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    user_id: int | None = Query(default=None, description="Requesting user ID if unauthenticated"),
) -> tuple[int, bool]:
    """Extracts (user_id, is_admin) either from Bearer token or query parameter."""
    if credentials and credentials.credentials:
        try:
            payload = decode_token(credentials.credentials)
            sub = payload.get("sub")
            role = payload.get("role", "user")
            if sub:
                uid = int(sub)
                is_admin = role == UserRole.ADMIN.value
                return uid, is_admin
        except jwt.PyJWTError as exc:
            raise UnauthorizedError(message="Invalid or expired access token") from exc

    if user_id is not None:
        return user_id, False

    raise UnauthorizedError(message="Authentication credentials or user_id required")

"""Unit tests for FastAPI dependency providers and security checks."""

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User, UserRole


@pytest.fixture
async def regular_user(db_session: AsyncSession) -> User:
    """Fixture creating active regular user."""
    user = User(
        email="regular_dep@example.com",
        hashed_password="pw",
        full_name="Regular Dep",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Fixture creating active admin user."""
    user = User(
        email="admin_dep@example.com",
        hashed_password="pw",
        full_name="Admin Dep",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_get_current_user_missing_credentials_raises_unauthorized(
    db_session: AsyncSession,
) -> None:
    """Verify missing credentials raise UnauthorizedError."""
    with pytest.raises(UnauthorizedError) as exc:
        await get_current_user(credentials=None, session=db_session)
    assert "Authentication credentials required" in exc.value.message


@pytest.mark.asyncio
async def test_get_current_user_invalid_token_raises_unauthorized(
    db_session: AsyncSession,
) -> None:
    """Verify invalid token string raises UnauthorizedError."""
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid.token.here")
    with pytest.raises(UnauthorizedError) as exc:
        await get_current_user(credentials=creds, session=db_session)
    assert "Invalid or expired access token" in exc.value.message


@pytest.mark.asyncio
async def test_get_current_user_refresh_token_rejected(db_session: AsyncSession, regular_user: User) -> None:
    """Verify providing a refresh token to access-only endpoint raises UnauthorizedError."""
    refresh_token_raw, _ = create_refresh_token(regular_user.id)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=refresh_token_raw)
    with pytest.raises(UnauthorizedError) as exc:
        await get_current_user(credentials=creds, session=db_session)
    assert "expected access token" in exc.value.message


@pytest.mark.asyncio
async def test_get_current_user_inactive_user_rejected(
    db_session: AsyncSession,
) -> None:
    """Verify deactivated user account is rejected."""
    user = User(
        email="inactive@example.com",
        hashed_password="pw",
        full_name="Inactive User",
        role=UserRole.USER,
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(user.id, role=user.role.value)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(UnauthorizedError) as exc:
        await get_current_user(credentials=creds, session=db_session)
    assert "deactivated" in exc.value.message


@pytest.mark.asyncio
async def test_get_current_user_happy_path(db_session: AsyncSession, regular_user: User) -> None:
    """Verify valid token resolves user entity."""
    token = create_access_token(regular_user.id, role=regular_user.role.value)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    resolved = await get_current_user(credentials=creds, session=db_session)
    assert resolved.id == regular_user.id
    assert resolved.email == regular_user.email


def test_require_role_admin_check(regular_user: User, admin_user: User) -> None:
    """Verify role check blocks regular user and allows admin."""
    admin_checker = require_role(UserRole.ADMIN)

    # Regular user fails
    with pytest.raises(ForbiddenError) as exc:
        admin_checker(current_user=regular_user)
    assert "Access forbidden" in exc.value.message

    # Admin user passes
    passed = admin_checker(current_user=admin_user)
    assert passed.id == admin_user.id

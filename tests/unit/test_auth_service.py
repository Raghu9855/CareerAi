"""Unit tests for AuthService business logic, rotation, revocation, and security boundaries."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, UnauthorizedError
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_auth_service_register_and_login_success(db_session: AsyncSession) -> None:
    """Verify registration creates user and tokens, and login returns valid token."""
    auth_service = AuthService(db_session)
    reg_req = RegisterRequest(
        email="service_user@example.com",
        password="ValidPassword123!",
        full_name="Service Candidate",
    )

    user, token = await auth_service.register(reg_req)
    assert user.id is not None
    assert user.email == "service_user@example.com"
    assert token.access_token is not None
    assert token.refresh_token is not None

    # Login with same credentials
    login_req = LoginRequest(email="service_user@example.com", password="ValidPassword123!")
    login_token = await auth_service.login(login_req)
    assert login_token.access_token is not None


@pytest.mark.asyncio
async def test_auth_service_duplicate_email_raises_conflict(db_session: AsyncSession) -> None:
    """Verify duplicate email throws ConflictError."""
    auth_service = AuthService(db_session)
    reg_req = RegisterRequest(
        email="dup_user@example.com",
        password="ValidPassword123!",
        full_name="Candidate A",
    )
    await auth_service.register(reg_req)

    with pytest.raises(ConflictError) as exc:
        await auth_service.register(reg_req)
    assert "already exists" in exc.value.message


@pytest.mark.asyncio
async def test_auth_service_login_invalid_password_raises_unauthorized(db_session: AsyncSession) -> None:
    """Verify wrong password raises UnauthorizedError."""
    auth_service = AuthService(db_session)
    await auth_service.register(
        RegisterRequest(email="wrongpass@example.com", password="CorrectPassword123!", full_name="User")
    )

    with pytest.raises(UnauthorizedError) as exc:
        await auth_service.login(LoginRequest(email="wrongpass@example.com", password="WrongPassword123!"))
    assert "Invalid email or password" in exc.value.message


@pytest.mark.asyncio
async def test_auth_service_login_nonexistent_user_raises_unauthorized(db_session: AsyncSession) -> None:
    """Verify nonexistent user raises UnauthorizedError."""
    auth_service = AuthService(db_session)
    with pytest.raises(UnauthorizedError) as exc:
        await auth_service.login(LoginRequest(email="nobody@example.com", password="Password123!"))
    assert "Invalid email or password" in exc.value.message


@pytest.mark.asyncio
async def test_auth_service_refresh_token_rotation_and_revocation(db_session: AsyncSession) -> None:
    """Verify refreshing tokens rotates refresh token and revoking rejects subsequent use."""
    auth_service = AuthService(db_session)
    _, initial_token = await auth_service.register(
        RegisterRequest(email="rotator@example.com", password="ValidPassword123!", full_name="Rotator")
    )

    # 1. Successful rotation
    rotated_token = await auth_service.refresh_tokens(initial_token.refresh_token)
    assert rotated_token.access_token is not None
    assert rotated_token.refresh_token != initial_token.refresh_token

    # 2. Old refresh token cannot be reused (replay detection)
    with pytest.raises(UnauthorizedError) as exc:
        await auth_service.refresh_tokens(initial_token.refresh_token)
    assert "revoked or expired" in exc.value.message

    # 3. Explicit logout revokes the current active refresh token
    await auth_service.logout(rotated_token.refresh_token)

    with pytest.raises(UnauthorizedError):
        await auth_service.refresh_tokens(rotated_token.refresh_token)


@pytest.mark.asyncio
async def test_auth_service_refresh_with_malformed_token(db_session: AsyncSession) -> None:
    """Verify malformed refresh token string raises UnauthorizedError."""
    auth_service = AuthService(db_session)
    with pytest.raises(UnauthorizedError) as exc:
        await auth_service.refresh_tokens("not.a.valid.jwt")
    assert "Invalid or expired" in exc.value.message

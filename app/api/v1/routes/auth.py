"""Authentication endpoints for registration, login, token rotation, and current user info."""

from fastapi import APIRouter, Depends, status

from app.api.deps import get_auth_service, get_current_user
from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshTokenRequest, RegisterRequest, Token
from app.schemas.common import MessageResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post(
    "/register",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(settings.RATE_LIMIT_AUTH_PER_MINUTE))],
    summary="User self-registration",
)
async def register(
    payload: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> dict:
    """Register a new user and return user profile with initial JWT access & refresh tokens."""
    user, tokens = await service.register(payload)
    return {
        "user": UserResponse.model_validate(user),
        "tokens": tokens.model_dump(),
    }


@router.post(
    "/login",
    response_model=Token,
    dependencies=[Depends(rate_limit(settings.RATE_LIMIT_AUTH_PER_MINUTE))],
    summary="Login with email and password",
)
async def login(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> Token:
    """Authenticate with email and password to receive JWT access and refresh tokens."""
    return await service.login(payload)


@router.post(
    "/refresh",
    response_model=Token,
    summary="Rotate refresh token and issue new access token",
)
async def refresh_tokens(
    payload: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service),
) -> Token:
    """Rotate an existing refresh token for a new access token and fresh refresh token."""
    return await service.refresh_tokens(payload.refresh_token)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke refresh token session",
)
async def logout(
    payload: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Revoke the given refresh token session."""
    await service.logout(payload.refresh_token)
    return MessageResponse(message="Successfully logged out and session revoked")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Retrieve identity and permissions for the currently authenticated bearer token."""
    return UserResponse.model_validate(current_user)

"""AuthService managing user authentication, token issuance, rotation, and revocation."""

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    hash_token,
    verify_password,
)
from app.models.token import RefreshToken
from app.models.user import User, UserRole
from app.repositories.token_repo import TokenRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, Token


class AuthService:
    """Business operations for authentication and JWT session management."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.token_repo = TokenRepository(session)
        self.settings = get_settings()

    async def register(self, payload: RegisterRequest) -> tuple[User, Token]:
        """Register a new user and generate access/refresh token pair."""
        email = payload.email.lower().strip()
        if await self.user_repo.email_exists(email):
            raise ConflictError(
                message=f"User with email '{email}' already exists",
                details={"email": email},
            )

        user = User(
            email=email,
            hashed_password=get_password_hash(payload.password),
            full_name=payload.full_name.strip(),
            role=UserRole.USER,
            is_active=True,
            is_verified=False,
        )
        created_user = await self.user_repo.create(user)
        token = await self._generate_tokens_for_user(created_user)
        return created_user, token

    async def login(self, payload: LoginRequest) -> Token:
        """Authenticate user credentials and issue token pair."""
        email = payload.email.lower().strip()
        user = await self.user_repo.get_by_email(email)

        if not user or not verify_password(payload.password, user.hashed_password):
            raise UnauthorizedError(
                message="Invalid email or password",
                details={"email": email},
            )

        if not user.is_active:
            raise UnauthorizedError(
                message="Account has been deactivated. Please contact support.",
                details={"user_id": user.id},
            )

        return await self._generate_tokens_for_user(user)

    async def refresh_tokens(self, refresh_token_raw: str) -> Token:
        """Validate, revoke old refresh token, and issue new rotated access and refresh token pair."""
        try:
            payload = decode_token(refresh_token_raw)
        except jwt.PyJWTError as exc:
            raise UnauthorizedError(message="Invalid or expired refresh token") from exc

        if payload.get("type") != "refresh":
            raise UnauthorizedError(message="Invalid token type: expected refresh token")

        sub = payload.get("sub")
        if not sub:
            raise UnauthorizedError(message="Malformed refresh token")

        user_id = int(sub)
        token_hash = hash_token(refresh_token_raw)

        # Verify token exists and is valid in database
        is_valid = await self.token_repo.is_valid(token_hash)
        if not is_valid:
            # If revoked token is reused, revoke all tokens for this user (replay attack detection)
            await self.token_repo.revoke_all_user_tokens(user_id)
            raise UnauthorizedError(message="Refresh token has been revoked or expired. Please re-authenticate.")

        # Revoke the old refresh token (Rotation)
        await self.token_repo.revoke_token(token_hash)

        # Verify user still exists and active
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedError(message="User account is no longer active")

        return await self._generate_tokens_for_user(user)

    async def logout(self, refresh_token_raw: str) -> None:
        """Revoke the provided refresh token session."""
        token_hash = hash_token(refresh_token_raw)
        await self.token_repo.revoke_token(token_hash)

    async def _generate_tokens_for_user(self, user: User) -> Token:
        """Internal helper to create access + refresh tokens and persist hashed refresh token."""
        access_token = create_access_token(subject=user.id, role=user.role.value)
        raw_refresh_token, expires_at = create_refresh_token(subject=user.id)

        token_record = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh_token),
            expires_at=expires_at,
            is_revoked=False,
        )
        await self.token_repo.create(token_record)

        return Token(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            token_type="bearer",
            expires_in=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

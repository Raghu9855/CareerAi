"""TokenRepository managing RefreshToken persistence, rotation, and revocation."""

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import RefreshToken
from app.repositories.base import BaseRepository


class TokenRepository(BaseRepository[RefreshToken]):
    """Data access repository for refresh tokens."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RefreshToken, session)

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        """Fetch token record by SHA-256 hash."""
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def revoke_token(self, token_hash: str) -> bool:
        """Mark specific token hash as revoked."""
        stmt = update(RefreshToken).where(RefreshToken.token_hash == token_hash).values(is_revoked=True)
        result = await self.session.execute(stmt)
        return bool(result.rowcount > 0)  # type: ignore[attr-defined]

    async def revoke_all_user_tokens(self, user_id: int) -> int:
        """Revoke all active tokens for a user (e.g. on logout all devices or password change)."""
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.is_revoked.is_(False))
            .values(is_revoked=True)
        )
        result = await self.session.execute(stmt)
        return int(result.rowcount)  # type: ignore[attr-defined]

    async def is_valid(self, token_hash: str) -> bool:
        """Check if a refresh token hash exists, is unrevoked, and not expired."""
        token = await self.get_by_token_hash(token_hash)
        if not token or token.is_revoked:
            return False
        return token.expires_at > datetime.now(UTC)

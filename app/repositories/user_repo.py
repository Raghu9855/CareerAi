"""UserRepository managing data access for User entities."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Data access repository for users."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        """Fetch user by unique email address."""
        stmt = select(User).where(User.email == email.lower().strip()).where(User.is_deleted.is_(False))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def email_exists(self, email: str, exclude_user_id: int | None = None) -> bool:
        """Check if an email is already registered."""
        stmt = select(User.id).where(User.email == email.lower().strip()).where(User.is_deleted.is_(False))
        if exclude_user_id:
            stmt = stmt.where(User.id != exclude_user_id)
        result = await self.session.execute(stmt)
        return result.scalar() is not None

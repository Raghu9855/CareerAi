"""ProfileRepository managing data access for User Profiles."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Profile
from app.repositories.base import BaseRepository


class ProfileRepository(BaseRepository[Profile]):
    """Data access repository for profiles."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Profile, session)

    async def get_by_user_id(self, user_id: int) -> Profile | None:
        """Fetch profile for a specific user."""
        stmt = select(Profile).where(Profile.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

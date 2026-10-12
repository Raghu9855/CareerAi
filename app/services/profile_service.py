"""ProfileService managing user profiles."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.profile import Profile
from app.repositories.profile_repo import ProfileRepository
from app.repositories.user_repo import UserRepository
from app.schemas.profile import ProfileCreate, ProfileUpdate


class ProfileService:
    """Business operations for user profiles."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.profile_repo = ProfileRepository(session)
        self.user_repo = UserRepository(session)

    async def get_profile(self, user_id: int) -> Profile:
        """Fetch profile for a user or raise NotFoundError."""
        profile = await self.profile_repo.get_by_user_id(user_id)
        if not profile:
            raise NotFoundError(
                message=f"Profile for user {user_id} not found",
                details={"user_id": user_id},
            )
        return profile

    async def create_or_update_profile(
        self,
        user_id: int,
        payload: ProfileCreate | ProfileUpdate,
    ) -> Profile:
        """Create a profile if none exists, or update existing profile attributes."""
        # Ensure user exists
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(message=f"User with ID {user_id} not found", details={"user_id": user_id})

        existing_profile = await self.profile_repo.get_by_user_id(user_id)
        data = payload.model_dump(exclude_unset=True)

        if existing_profile:
            return await self.profile_repo.update(existing_profile, data)

        new_profile = Profile(user_id=user_id, **data)
        return await self.profile_repo.create(new_profile)

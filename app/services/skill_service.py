"""SkillService managing the global taxonomy and user-associated skills."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models.skill import Skill, UserSkill
from app.repositories.skill_repo import SkillRepository, UserSkillRepository
from app.repositories.user_repo import UserRepository
from app.schemas.common import PaginationParams
from app.schemas.skill import SkillCreate, SkillUpdate, UserSkillCreate, UserSkillUpdate


class SkillService:
    """Business operations for skills taxonomy and user skill assignments."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.skill_repo = SkillRepository(session)
        self.user_skill_repo = UserSkillRepository(session)
        self.user_repo = UserRepository(session)

    async def list_skills(
        self,
        params: PaginationParams,
        category: str | None = None,
    ) -> tuple[Sequence[Skill], int]:
        """List skills in taxonomy with optional category filtering."""
        filters = []
        if category:
            filters.append(Skill.category == category)
        items = await self.skill_repo.list(
            *filters,
            offset=params.offset,
            limit=params.per_page,
        )
        total = await self.skill_repo.count(*filters)
        return items, total

    async def create_skill(self, payload: SkillCreate) -> Skill:
        """Create a new skill if not already present."""
        cleaned_name = payload.name.strip()
        normalized = cleaned_name.lower().replace(" ", "_")
        existing = await self.skill_repo.get_by_normalized_name(normalized)
        if existing:
            raise ConflictError(
                message=f"Skill '{cleaned_name}' already exists",
                details={"name": cleaned_name},
            )
        skill = Skill(name=cleaned_name, category=payload.category.strip(), normalized_name=normalized)
        return await self.skill_repo.create(skill)

    async def update_skill(self, skill_id: int, payload: SkillUpdate) -> Skill:
        """Update skill attributes."""
        skill = await self.skill_repo.get_by_id(skill_id)
        if not skill:
            raise NotFoundError(message=f"Skill {skill_id} not found", details={"skill_id": skill_id})
        update_data = payload.model_dump(exclude_unset=True)
        if "name" in update_data and update_data["name"]:
            update_data["normalized_name"] = update_data["name"].strip().lower().replace(" ", "_")
        return await self.skill_repo.update(skill, update_data)

    async def add_user_skill(self, user_id: int, payload: UserSkillCreate) -> UserSkill:
        """Associate a skill with a user."""
        # Verify user exists
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(message=f"User {user_id} not found", details={"user_id": user_id})

        # Verify skill exists
        skill = await self.skill_repo.get_by_id(payload.skill_id)
        if not skill:
            raise NotFoundError(
                message=f"Skill {payload.skill_id} not found",
                details={"skill_id": payload.skill_id},
            )

        # Check if already added
        existing = await self.user_skill_repo.get_by_user_and_skill(user_id, payload.skill_id)
        if existing:
            raise ConflictError(
                message=f"Skill '{skill.name}' is already attached to this profile",
                details={"skill_id": payload.skill_id},
            )

        user_skill = UserSkill(
            user_id=user_id,
            skill_id=payload.skill_id,
            proficiency=payload.proficiency,
            years_of_experience=payload.years_of_experience,
        )
        created = await self.user_skill_repo.create(user_skill)
        # Fetch with eager loaded skill relation
        reloaded = await self.user_skill_repo.get_by_user_and_skill(user_id, payload.skill_id)
        return reloaded or created

    async def list_user_skills(self, user_id: int) -> Sequence[UserSkill]:
        """Fetch all skills attached to a user."""
        return await self.user_skill_repo.list_by_user(user_id)

    async def update_user_skill(
        self,
        user_id: int,
        skill_id: int,
        payload: UserSkillUpdate,
    ) -> UserSkill:
        """Update proficiency or experience of an attached skill."""
        user_skill = await self.user_skill_repo.get_by_user_and_skill(user_id, skill_id)
        if not user_skill:
            raise NotFoundError(
                message=f"User skill association not found for skill ID {skill_id}",
                details={"user_id": user_id, "skill_id": skill_id},
            )
        data = payload.model_dump(exclude_unset=True)
        updated = await self.user_skill_repo.update(user_skill, data)
        reloaded = await self.user_skill_repo.get_by_user_and_skill(user_id, skill_id)
        return reloaded or updated

    async def remove_user_skill(self, user_id: int, skill_id: int) -> None:
        """Remove a skill from the user's profile."""
        user_skill = await self.user_skill_repo.get_by_user_and_skill(user_id, skill_id)
        if not user_skill:
            raise NotFoundError(
                message=f"User skill association not found for skill ID {skill_id}",
                details={"user_id": user_id, "skill_id": skill_id},
            )
        await self.user_skill_repo.delete(user_skill, soft=False)

"""SkillRepository and UserSkillRepository managing skills and user proficiencies."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.skill import Skill, UserSkill
from app.repositories.base import BaseRepository


class SkillRepository(BaseRepository[Skill]):
    """Data access repository for the global skills taxonomy."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Skill, session)

    async def get_by_name(self, name: str) -> Skill | None:
        """Find skill by case-insensitive name."""
        stmt = select(Skill).where(Skill.name.ilike(name.strip()))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_normalized_name(self, normalized_name: str) -> Skill | None:
        """Find skill by normalized slug."""
        stmt = select(Skill).where(Skill.normalized_name == normalized_name.lower().strip())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_or_create(self, name: str, category: str = "General") -> Skill:
        """Retrieve existing skill or register new entry."""
        cleaned_name = name.strip()
        normalized = cleaned_name.lower().replace(" ", "_")
        existing = await self.get_by_normalized_name(normalized)
        if existing:
            return existing

        new_skill = Skill(name=cleaned_name, category=category, normalized_name=normalized)
        return await self.create(new_skill)


class UserSkillRepository(BaseRepository[UserSkill]):
    """Data access repository for user skills associations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(UserSkill, session)

    async def get_by_user_and_skill(self, user_id: int, skill_id: int) -> UserSkill | None:
        """Retrieve specific user skill association."""
        stmt = (
            select(UserSkill)
            .options(selectinload(UserSkill.skill))
            .where(UserSkill.user_id == user_id, UserSkill.skill_id == skill_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_user(self, user_id: int) -> Sequence[UserSkill]:
        """Retrieve all skills associated with a user."""
        stmt = (
            select(UserSkill)
            .options(selectinload(UserSkill.skill))
            .where(UserSkill.user_id == user_id)
            .order_by(UserSkill.id.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

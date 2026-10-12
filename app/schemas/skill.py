"""Pydantic schemas for Skill and UserSkill entities."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.skill import ProficiencyLevel


class SkillBase(BaseModel):
    """Base skill attributes."""

    name: str = Field(min_length=1, max_length=100)
    category: str = Field(default="General", max_length=100)


class SkillCreate(SkillBase):
    """Payload to register a new skill."""

    pass


class SkillUpdate(BaseModel):
    """Payload to update an existing skill."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: str | None = Field(default=None, max_length=100)


class SkillResponse(SkillBase):
    """Skill response representation."""

    id: int
    normalized_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserSkillCreate(BaseModel):
    """Payload to attach a skill to the user's profile."""

    skill_id: int
    proficiency: ProficiencyLevel = Field(default=ProficiencyLevel.INTERMEDIATE)
    years_of_experience: float | None = Field(default=1.0, ge=0)


class UserSkillUpdate(BaseModel):
    """Payload to update an attached user skill."""

    proficiency: ProficiencyLevel | None = None
    years_of_experience: float | None = Field(default=None, ge=0)


class UserSkillResponse(BaseModel):
    """Representation of a user's associated skill."""

    id: int
    user_id: int
    skill_id: int
    proficiency: ProficiencyLevel
    years_of_experience: float | None
    created_at: datetime
    skill: SkillResponse | None = None

    model_config = ConfigDict(from_attributes=True)

"""Central Pydantic schemas registry."""

from app.schemas.application import (
    ApplicationCreate,
    ApplicationFilter,
    ApplicationResponse,
    ApplicationUpdate,
)
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.job import JobCreate, JobFilter, JobResponse, JobUpdate
from app.schemas.profile import ProfileCreate, ProfileResponse, ProfileUpdate
from app.schemas.skill import (
    SkillCreate,
    SkillResponse,
    SkillUpdate,
    UserSkillCreate,
    UserSkillResponse,
    UserSkillUpdate,
)
from app.schemas.user import UserCreate, UserResponse, UserUpdate

__all__ = [
    "PaginationParams",
    "PaginatedResponse",
    "MessageResponse",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "ProfileCreate",
    "ProfileUpdate",
    "ProfileResponse",
    "SkillCreate",
    "SkillUpdate",
    "SkillResponse",
    "UserSkillCreate",
    "UserSkillUpdate",
    "UserSkillResponse",
    "JobCreate",
    "JobUpdate",
    "JobFilter",
    "JobResponse",
    "ApplicationCreate",
    "ApplicationUpdate",
    "ApplicationFilter",
    "ApplicationResponse",
]

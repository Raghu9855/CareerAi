"""Skills taxonomy and user skills management endpoints."""

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_skill_service
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.skill import (
    SkillCreate,
    SkillResponse,
    SkillUpdate,
    UserSkillCreate,
    UserSkillResponse,
    UserSkillUpdate,
)
from app.services.skill_service import SkillService

router = APIRouter(prefix="/skills", tags=["Skills"])


@router.get("", response_model=PaginatedResponse[SkillResponse], summary="List taxonomy skills")
async def list_skills(
    category: str | None = Query(default=None, description="Filter by skill category"),
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=50, ge=1, le=100, description="Items per page"),
    service: SkillService = Depends(get_skill_service),
) -> PaginatedResponse[SkillResponse]:
    """Retrieve paginated skills from the global taxonomy."""
    params = PaginationParams(page=page, per_page=per_page)
    skills, total = await service.list_skills(params, category=category)
    items = [SkillResponse.model_validate(s) for s in skills]
    return PaginatedResponse.create(items=items, total=total, params=params)


@router.post(
    "",
    response_model=SkillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add skill to taxonomy",
)
async def create_skill(
    payload: SkillCreate,
    service: SkillService = Depends(get_skill_service),
) -> SkillResponse:
    """Register a new skill in the taxonomy."""
    skill = await service.create_skill(payload)
    return SkillResponse.model_validate(skill)


@router.put("/{skill_id}", response_model=SkillResponse, summary="Update skill in taxonomy")
async def update_skill(
    skill_id: int,
    payload: SkillUpdate,
    service: SkillService = Depends(get_skill_service),
) -> SkillResponse:
    """Update taxonomy skill metadata."""
    skill = await service.update_skill(skill_id, payload)
    return SkillResponse.model_validate(skill)


@router.get("/users/{user_id}", response_model=list[UserSkillResponse], summary="List user's skills")
async def list_user_skills(
    user_id: int,
    service: SkillService = Depends(get_skill_service),
) -> list[UserSkillResponse]:
    """Retrieve all skills attached to a user's profile."""
    skills = await service.list_user_skills(user_id)
    return [UserSkillResponse.model_validate(s) for s in skills]


@router.post(
    "/users/{user_id}",
    response_model=UserSkillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add skill to user profile",
)
async def add_user_skill(
    user_id: int,
    payload: UserSkillCreate,
    service: SkillService = Depends(get_skill_service),
) -> UserSkillResponse:
    """Associate a taxonomy skill with a user's profile with proficiency rating."""
    user_skill = await service.add_user_skill(user_id, payload)
    return UserSkillResponse.model_validate(user_skill)


@router.put("/users/{user_id}/{skill_id}", response_model=UserSkillResponse, summary="Update user skill")
async def update_user_skill(
    user_id: int,
    skill_id: int,
    payload: UserSkillUpdate,
    service: SkillService = Depends(get_skill_service),
) -> UserSkillResponse:
    """Update proficiency or years of experience for a user's skill."""
    user_skill = await service.update_user_skill(user_id, skill_id, payload)
    return UserSkillResponse.model_validate(user_skill)


@router.delete(
    "/users/{user_id}/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove skill from user profile",
)
async def remove_user_skill(
    user_id: int,
    skill_id: int,
    service: SkillService = Depends(get_skill_service),
) -> None:
    """Remove a skill from a user's profile."""
    await service.remove_user_skill(user_id, skill_id)

"""Profile management endpoints."""

from fastapi import APIRouter, Depends, status

from app.api.deps import get_profile_service
from app.schemas.profile import ProfileCreate, ProfileResponse, ProfileUpdate
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profiles", tags=["Profiles"])


@router.get("/{user_id}", response_model=ProfileResponse, summary="Get user profile")
async def get_profile(
    user_id: int,
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    """Retrieve professional profile for a specific user."""
    profile = await service.get_profile(user_id)
    return ProfileResponse.model_validate(profile)


@router.post(
    "/{user_id}",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create profile",
)
async def create_profile(
    user_id: int,
    payload: ProfileCreate,
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    """Create or initialize a professional profile for a user."""
    profile = await service.create_or_update_profile(user_id, payload)
    return ProfileResponse.model_validate(profile)


@router.put("/{user_id}", response_model=ProfileResponse, summary="Update profile")
async def update_profile(
    user_id: int,
    payload: ProfileUpdate,
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    """Update existing profile details."""
    profile = await service.create_or_update_profile(user_id, payload)
    return ProfileResponse.model_validate(profile)

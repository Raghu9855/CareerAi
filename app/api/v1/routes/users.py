"""User management endpoints."""

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_user_service
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
)
async def create_user(
    payload: UserCreate,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Register a new user account."""
    user = await service.create_user(payload)
    return UserResponse.model_validate(user)


@router.get("", response_model=PaginatedResponse[UserResponse], summary="List users")
async def list_users(
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page"),
    service: UserService = Depends(get_user_service),
) -> PaginatedResponse[UserResponse]:
    """Retrieve a paginated list of user accounts."""
    params = PaginationParams(page=page, per_page=per_page)
    users, total = await service.list_users(params)
    items = [UserResponse.model_validate(u) for u in users]
    return PaginatedResponse.create(items=items, total=total, params=params)


@router.get("/{user_id}", response_model=UserResponse, summary="Get user by ID")
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Retrieve details for a specific user."""
    user = await service.get_user_by_id(user_id)
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse, summary="Update user")
async def update_user(
    user_id: int,
    payload: UserUpdate,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Update profile attributes for a specific user."""
    user = await service.update_user(user_id, payload)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete user")
async def delete_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
) -> None:
    """Soft delete a user account."""
    await service.delete_user(user_id)

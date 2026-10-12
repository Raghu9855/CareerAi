"""Pydantic schemas for User entity."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    """Base user attributes."""

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)


class UserCreate(UserBase):
    """Payload for creating a new user."""

    password: str = Field(min_length=8, max_length=128, description="Plaintext password (min 8 chars)")
    role: UserRole = Field(default=UserRole.USER)


class UserUpdate(BaseModel):
    """Payload for updating an existing user."""

    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None
    role: UserRole | None = None


class UserResponse(UserBase):
    """User response model."""

    id: int
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

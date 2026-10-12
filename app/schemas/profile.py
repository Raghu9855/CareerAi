"""Pydantic schemas for Profile entity."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProfileBase(BaseModel):
    """Base profile attributes."""

    headline: str | None = Field(default=None, max_length=255)
    summary: str | None = None
    location: str | None = Field(default=None, max_length=255)
    years_of_experience: float | None = Field(default=0.0, ge=0)
    linkedin_url: str | None = Field(default=None, max_length=255)
    github_url: str | None = Field(default=None, max_length=255)
    website_url: str | None = Field(default=None, max_length=255)


class ProfileCreate(ProfileBase):
    """Payload for creating or initializing a user profile."""

    pass


class ProfileUpdate(BaseModel):
    """Payload for updating an existing profile."""

    headline: str | None = Field(default=None, max_length=255)
    summary: str | None = None
    location: str | None = Field(default=None, max_length=255)
    years_of_experience: float | None = Field(default=None, ge=0)
    linkedin_url: str | None = Field(default=None, max_length=255)
    github_url: str | None = Field(default=None, max_length=255)
    website_url: str | None = Field(default=None, max_length=255)


class ProfileResponse(ProfileBase):
    """Profile response representation."""

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

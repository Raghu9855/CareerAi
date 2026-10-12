"""Authentication request and response Pydantic schemas."""

from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    """JWT Token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    """User credentials login request."""

    email: EmailStr
    password: str = Field(min_length=1)


class RefreshTokenRequest(BaseModel):
    """Token rotation payload."""

    refresh_token: str


class RegisterRequest(BaseModel):
    """New user self-registration payload."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)

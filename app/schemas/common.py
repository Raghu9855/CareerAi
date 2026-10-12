"""Common shared Pydantic schemas for pagination, sorting, and standard responses."""

import math
from typing import TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for pagination."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


class PaginatedResponse[T](BaseModel):
    """Generic envelope for paginated collections."""

    items: list[T]
    total: int
    page: int
    per_page: int
    total_pages: int

    @classmethod
    def create(cls, items: list[T], total: int, params: PaginationParams) -> "PaginatedResponse[T]":
        total_pages = math.ceil(total / params.per_page) if total > 0 else 0
        return cls(
            items=items,
            total=total,
            page=params.page,
            per_page=params.per_page,
            total_pages=total_pages,
        )


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
    success: bool = True

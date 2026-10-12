"""Pydantic schemas for Application tracking."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.application import ApplicationStatus
from app.schemas.job import JobResponse


class ApplicationCreate(BaseModel):
    """Payload to apply to or track a job."""

    job_id: int
    notes: str | None = None


class ApplicationUpdate(BaseModel):
    """Payload to update an application status or notes."""

    status: ApplicationStatus | None = None
    notes: str | None = None


class ApplicationFilter(BaseModel):
    """Filter criteria for job applications."""

    status: ApplicationStatus | None = None
    job_id: int | None = None


class ApplicationResponse(BaseModel):
    """Job application response model."""

    id: int
    user_id: int
    job_id: int
    status: ApplicationStatus
    applied_at: datetime
    notes: str | None
    created_at: datetime
    updated_at: datetime
    job: JobResponse | None = None

    model_config = ConfigDict(from_attributes=True)

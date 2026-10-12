"""Pydantic schemas for Job postings."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import JobStatus, JobType


class JobBase(BaseModel):
    """Base job posting attributes."""

    title: str = Field(min_length=1, max_length=255)
    company: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=10)
    location: str | None = Field(default="Remote", max_length=255)
    job_type: JobType = Field(default=JobType.FULL_TIME)
    status: JobStatus = Field(default=JobStatus.OPEN)
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", max_length=10)


class JobCreate(JobBase):
    """Payload to create a new job posting."""

    pass


class JobUpdate(BaseModel):
    """Payload to update an existing job posting."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    company: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=10)
    location: str | None = Field(default=None, max_length=255)
    job_type: JobType | None = None
    status: JobStatus | None = None
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=10)


class JobFilter(BaseModel):
    """Filter criteria for job queries."""

    search: str | None = None
    location: str | None = None
    job_type: JobType | None = None
    status: JobStatus | None = None


class JobResponse(JobBase):
    """Job posting response representation."""

    id: int
    created_by_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

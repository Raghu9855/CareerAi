"""Job postings and listings endpoints."""

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_job_service
from app.models.job import JobStatus, JobType
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.job import JobCreate, JobFilter, JobResponse, JobUpdate
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create job posting",
)
async def create_job(
    payload: JobCreate,
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    """Publish a new job listing."""
    job = await service.create_job(payload)
    return JobResponse.model_validate(job)


@router.get("", response_model=PaginatedResponse[JobResponse], summary="List and filter job postings")
async def list_jobs(
    search: str | None = Query(default=None, description="Keyword search in title, company, description"),
    location: str | None = Query(default=None, description="Location filter"),
    job_type: JobType | None = Query(default=None, description="Employment type"),
    status_filter: JobStatus | None = Query(default=None, alias="status", description="Publication status"),
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page"),
    service: JobService = Depends(get_job_service),
) -> PaginatedResponse[JobResponse]:
    """Retrieve paginated job postings matching search and filter criteria."""
    filters = JobFilter(search=search, location=location, job_type=job_type, status=status_filter)
    params = PaginationParams(page=page, per_page=per_page)
    jobs, total = await service.list_jobs(filters, params)
    items = [JobResponse.model_validate(j) for j in jobs]
    return PaginatedResponse.create(items=items, total=total, params=params)


@router.get("/{job_id}", response_model=JobResponse, summary="Get job by ID")
async def get_job(
    job_id: int,
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    """Retrieve full details for a single job posting."""
    job = await service.get_job(job_id)
    return JobResponse.model_validate(job)


@router.put("/{job_id}", response_model=JobResponse, summary="Update job posting")
async def update_job(
    job_id: int,
    payload: JobUpdate,
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    """Update fields on an existing job posting."""
    job = await service.update_job(job_id, payload)
    return JobResponse.model_validate(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete job posting")
async def delete_job(
    job_id: int,
    service: JobService = Depends(get_job_service),
) -> None:
    """Soft delete a job posting."""
    await service.delete_job(job_id)

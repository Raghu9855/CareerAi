"""JobService managing job listings and search operations."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.models.job import Job
from app.repositories.job_repo import JobRepository
from app.schemas.common import PaginationParams
from app.schemas.job import JobCreate, JobFilter, JobUpdate


class JobService:
    """Business operations for job postings."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = JobRepository(session)

    async def create_job(self, payload: JobCreate, created_by_id: int | None = None) -> Job:
        """Create a new job posting with salary validation."""
        if (
            payload.salary_min is not None
            and payload.salary_max is not None
            and payload.salary_min > payload.salary_max
        ):
            raise ValidationError(
                message="Minimum salary cannot exceed maximum salary",
                details={"salary_min": payload.salary_min, "salary_max": payload.salary_max},
            )

        job_data = payload.model_dump()
        job = Job(**job_data, created_by_id=created_by_id)
        return await self.repo.create(job)

    async def get_job(self, job_id: int) -> Job:
        """Retrieve job posting or raise NotFoundError."""
        job = await self.repo.get_by_id(job_id)
        if not job:
            raise NotFoundError(message=f"Job with ID {job_id} not found", details={"job_id": job_id})
        return job

    async def list_jobs(
        self,
        filters: JobFilter,
        params: PaginationParams,
    ) -> tuple[Sequence[Job], int]:
        """Search and filter job postings with pagination."""
        return await self.repo.search_jobs(
            filters=filters,
            offset=params.offset,
            limit=params.per_page,
        )

    async def update_job(self, job_id: int, payload: JobUpdate) -> Job:
        """Update existing job posting attributes."""
        job = await self.get_job(job_id)

        update_data = payload.model_dump(exclude_unset=True)

        min_sal = update_data.get("salary_min", job.salary_min)
        max_sal = update_data.get("salary_max", job.salary_max)
        if min_sal is not None and max_sal is not None and min_sal > max_sal:
            raise ValidationError(
                message="Minimum salary cannot exceed maximum salary",
                details={"salary_min": min_sal, "salary_max": max_sal},
            )

        return await self.repo.update(job, update_data)

    async def delete_job(self, job_id: int) -> None:
        """Soft-delete job posting."""
        job = await self.get_job(job_id)
        await self.repo.delete(job, soft=True)

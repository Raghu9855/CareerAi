"""JobRepository managing job postings and multi-field search."""

from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from app.repositories.base import BaseRepository
from app.schemas.job import JobFilter


class JobRepository(BaseRepository[Job]):
    """Data access repository for jobs."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Job, session)

    async def search_jobs(
        self,
        filters: JobFilter,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Job], int]:
        """Query jobs with full search filtering and pagination."""
        stmt = select(Job).where(Job.is_deleted.is_(False))
        count_stmt = select(func.count()).select_from(Job).where(Job.is_deleted.is_(False))

        conditions = []

        if filters.search:
            pattern = f"%{filters.search.strip()}%"
            conditions.append(
                or_(
                    Job.title.ilike(pattern),
                    Job.company.ilike(pattern),
                    Job.description.ilike(pattern),
                )
            )

        if filters.location:
            conditions.append(Job.location.ilike(f"%{filters.location.strip()}%"))

        if filters.job_type:
            conditions.append(Job.job_type == filters.job_type)

        if filters.status:
            conditions.append(Job.status == filters.status)
        else:
            # Default to open jobs for public listings
            conditions.append(Job.status == JobStatus.OPEN)

        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(Job.created_at.desc()).offset(offset).limit(limit)
        items_res = await self.session.execute(stmt)
        items = items_res.scalars().all()

        return items, total

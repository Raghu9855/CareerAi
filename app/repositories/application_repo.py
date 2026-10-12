"""ApplicationRepository managing job application pipeline records."""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.repositories.base import BaseRepository
from app.schemas.application import ApplicationFilter


class ApplicationRepository(BaseRepository[Application]):
    """Data access repository for job applications."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Application, session)

    async def get_by_user_and_job(self, user_id: int, job_id: int) -> Application | None:
        """Check if an application already exists for this user and job."""
        stmt = select(Application).where(
            Application.user_id == user_id,
            Application.job_id == job_id,
            Application.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_with_job(self, application_id: int) -> Application | None:
        """Fetch application with eager-loaded job details."""
        stmt = (
            select(Application)
            .options(selectinload(Application.job))
            .where(
                Application.id == application_id,
                Application.is_deleted.is_(False),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_user(
        self,
        user_id: int,
        filters: ApplicationFilter,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Application], int]:
        """Fetch paginated applications for a specific user with filter criteria."""
        stmt = (
            select(Application)
            .options(selectinload(Application.job))
            .where(
                Application.user_id == user_id,
                Application.is_deleted.is_(False),
            )
        )
        count_stmt = (
            select(func.count())
            .select_from(Application)
            .where(
                Application.user_id == user_id,
                Application.is_deleted.is_(False),
            )
        )

        conditions = []
        if filters.status:
            conditions.append(Application.status == filters.status)
        if filters.job_id:
            conditions.append(Application.job_id == filters.job_id)

        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(Application.applied_at.desc()).offset(offset).limit(limit)
        items_res = await self.session.execute(stmt)
        items = items_res.scalars().all()

        return items, total

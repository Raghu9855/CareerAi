"""Repository for Analysis database operations."""

from collections.abc import Sequence

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import Analysis
from app.repositories.base import BaseRepository
from app.schemas.common import PaginationParams


class AnalysisRepository(BaseRepository[Analysis]):
    """Data access layer for candidate-job compatibility analyses."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Analysis, session)

    async def list_by_user(
        self,
        user_id: int,
        params: PaginationParams,
    ) -> tuple[Sequence[Analysis], int]:
        """Fetch paginated analyses scoped to a specific user."""
        stmt = (
            select(Analysis)
            .where(Analysis.user_id == user_id, Analysis.is_deleted.is_(False))
            .order_by(desc(Analysis.created_at))
            .offset(params.offset)
            .limit(params.limit)
        )
        result = await self.session.execute(stmt)
        items = result.scalars().all()

        count_stmt = select(func.count(Analysis.id)).where(Analysis.user_id == user_id, Analysis.is_deleted.is_(False))
        total = (await self.session.execute(count_stmt)).scalar_one()

        return items, total

    async def get_by_user_and_id(
        self,
        analysis_id: int,
        user_id: int,
    ) -> Analysis | None:
        """Fetch a specific analysis ensuring ownership."""
        stmt = select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.user_id == user_id,
            Analysis.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

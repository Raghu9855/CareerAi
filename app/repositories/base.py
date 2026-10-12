"""Generic asynchronous BaseRepository with SQLAlchemy 2.0."""

from collections.abc import Sequence
from typing import Any, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base, SoftDeleteMixin

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository[ModelType: Base]:
    """Generic repository providing standardized asynchronous CRUD operations."""

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get_by_id(self, id: int) -> ModelType | None:
        """Fetch entity by primary key, respecting soft-delete if applicable."""
        stmt = select(self.model).where(self.model.id == id)  # type: ignore[attr-defined]
        if issubclass(self.model, SoftDeleteMixin):
            stmt = stmt.where(self.model.is_deleted.is_(False))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list(
        self,
        *filters: Any,
        offset: int = 0,
        limit: int = 20,
        order_by: Any = None,
    ) -> Sequence[ModelType]:
        """Retrieve a paginated list of entities matching filters."""
        stmt = select(self.model)
        if issubclass(self.model, SoftDeleteMixin):
            stmt = stmt.where(self.model.is_deleted.is_(False))
        if filters:
            stmt = stmt.where(*filters)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        else:
            if hasattr(self.model, "id"):
                stmt = stmt.order_by(self.model.id.desc())  # type: ignore[attr-defined]
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self, *filters: Any) -> int:
        """Count total matching rows."""
        stmt = select(func.count()).select_from(self.model)
        if issubclass(self.model, SoftDeleteMixin):
            stmt = stmt.where(self.model.is_deleted.is_(False))
        if filters:
            stmt = stmt.where(*filters)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def create(self, instance: ModelType) -> ModelType:
        """Persist a new entity instance to the database."""
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, instance: ModelType, attributes: dict[str, Any]) -> ModelType:
        """Apply an attributes dictionary to an existing entity instance."""
        for key, value in attributes.items():
            if hasattr(instance, key) and value is not None:
                setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, instance: ModelType, soft: bool = True) -> None:
        """Remove entity either via soft delete or hard delete."""
        if soft and isinstance(instance, SoftDeleteMixin):
            instance.soft_delete()
            await self.session.flush()
        else:
            await self.session.delete(instance)
            await self.session.flush()

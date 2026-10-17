"""DocumentRepository managing persistence for uploaded documents and text chunks."""

from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentStatus
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    """Data access repository for career documents."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Document, session)

    async def get_by_id_and_user(self, document_id: int, user_id: int) -> Document | None:
        """Fetch document by ID strictly verifying tenant user ID."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
            Document.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_user(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Document], int]:
        """Fetch paginated documents belonging to a user."""
        stmt = (
            select(Document)
            .where(
                Document.user_id == user_id,
                Document.is_deleted.is_(False),
            )
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = (
            select(func.count())
            .select_from(Document)
            .where(
                Document.user_id == user_id,
                Document.is_deleted.is_(False),
            )
        )

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        items_res = await self.session.execute(stmt)
        items = items_res.scalars().all()

        return items, total

    async def update_status(
        self,
        document_id: int,
        status: DocumentStatus,
        extracted_text: str | None = None,
        error_message: str | None = None,
    ) -> Document | None:
        """Update extraction pipeline status and text content."""
        update_vals: dict = {"status": status}
        if extracted_text is not None:
            update_vals["extracted_text"] = extracted_text
            update_vals["char_count"] = len(extracted_text)
        if error_message is not None:
            update_vals["error_message"] = error_message

        stmt = update(Document).where(Document.id == document_id).values(**update_vals)
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get_by_id(document_id)

    async def create_chunks(self, chunks: list[DocumentChunk]) -> None:
        """Batch insert document text chunks."""
        for chunk in chunks:
            self.session.add(chunk)
        await self.session.flush()

    async def delete_chunks_by_document(self, document_id: int) -> int:
        """Remove all text chunks for a document."""
        stmt = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        res = await self.session.execute(stmt)
        chunks = res.scalars().all()
        for c in chunks:
            await self.session.delete(c)
        await self.session.flush()
        return len(chunks)

"""DocumentService managing upload validation, storage persistence, and text extraction."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.document import Document, DocumentStatus, DocumentType
from app.repositories.document_repo import DocumentRepository
from app.schemas.common import PaginationParams
from app.services.document_validator import validate_document
from app.services.storage import get_storage_backend
from app.services.text_extraction import extract_text

logger = get_logger("careerai.documents")


class DocumentService:
    """Business operations for career documents and resumes."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = DocumentRepository(session)
        self.storage = get_storage_backend()

    async def upload_document(
        self,
        user_id: int,
        filename: str,
        content_type: str,
        file_bytes: bytes,
        doc_type: DocumentType = DocumentType.RESUME,
        process_sync: bool = True,
    ) -> Document:
        """
        Validate, save file to storage backend, and register document in database.
        Optionally processes text extraction synchronously or via background task.
        """
        # 1. Validation (size, extension, MIME, magic bytes, safe filename)
        safe_name, ext = validate_document(filename, content_type, file_bytes)

        # 2. Persist to storage backend (Local filesystem or S3)
        storage_path = await self.storage.save(file_bytes, safe_name, content_type)

        # 3. Create document record
        document = Document(
            user_id=user_id,
            filename=safe_name,
            storage_path=storage_path,
            mime_type=content_type,
            file_size=len(file_bytes),
            doc_type=doc_type,
            status=DocumentStatus.UPLOADED,
        )
        created_doc = await self.repo.create(document)

        # 4. Extract text pipeline
        if process_sync:
            await self.process_document_text(created_doc.id, file_bytes, ext)
            reloaded = await self.repo.get_by_id(created_doc.id)
            return reloaded or created_doc

        return created_doc

    async def process_document_text(
        self,
        document_id: int,
        file_bytes: bytes,
        extension: str,
    ) -> None:
        """Extract text from document and transition status through processing -> ready/failed."""
        logger.info(f"Starting text extraction for document {document_id}")
        await self.repo.update_status(document_id, DocumentStatus.PROCESSING)

        try:
            extracted_text = extract_text(file_bytes, extension)
            await self.repo.update_status(
                document_id,
                DocumentStatus.READY,
                extracted_text=extracted_text,
            )
            logger.info(f"Document {document_id} extraction succeeded ({len(extracted_text)} chars)")
        except Exception as exc:
            logger.error(f"Text extraction failed for document {document_id}: {exc}")
            await self.repo.update_status(
                document_id,
                DocumentStatus.FAILED,
                error_message=str(exc)[:500],
            )

    async def get_document(
        self,
        document_id: int,
        user_id: int,
        is_admin: bool = False,
    ) -> Document:
        """Retrieve document metadata enforcing tenant ownership checks."""
        doc = await self.repo.get_by_id(document_id)
        if not doc or doc.is_deleted:
            raise NotFoundError(message=f"Document {document_id} not found", details={"document_id": document_id})

        if not is_admin and doc.user_id != user_id:
            raise ForbiddenError(
                message="You do not have permission to access this document",
                details={"document_id": document_id},
            )

        return doc

    async def list_documents(
        self,
        user_id: int,
        params: PaginationParams,
    ) -> tuple[Sequence[Document], int]:
        """List documents strictly scoped to requesting user."""
        return await self.repo.list_by_user(
            user_id=user_id,
            offset=params.offset,
            limit=params.per_page,
        )

    async def download_document(
        self,
        document_id: int,
        user_id: int,
        is_admin: bool = False,
    ) -> tuple[bytes, str, str]:
        """Download raw file bytes with ownership verification."""
        doc = await self.get_document(document_id, user_id, is_admin=is_admin)
        file_bytes = await self.storage.get(doc.storage_path)
        return file_bytes, doc.filename, doc.mime_type

    async def delete_document(
        self,
        document_id: int,
        user_id: int,
        is_admin: bool = False,
    ) -> None:
        """Delete document file from storage, clean chunks, and soft-delete DB record."""
        doc = await self.get_document(document_id, user_id, is_admin=is_admin)

        # Remove from storage
        await self.storage.delete(doc.storage_path)

        # Remove chunks
        await self.repo.delete_chunks_by_document(document_id)

        # Soft delete record
        await self.repo.delete(doc, soft=True)

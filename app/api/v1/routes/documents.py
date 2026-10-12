"""Document and resume management endpoints: upload, status tracking, download, and deletion."""

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Response,
    UploadFile,
    status,
)

from app.api.deps import get_document_service, get_requesting_user_or_id
from app.models.document import DocumentType
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.document import DocumentResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload resume or career document",
)
async def upload_document(
    file: UploadFile = File(..., description="Document file (PDF, DOCX, TXT max 10MB)"),
    doc_type: DocumentType = Form(default=DocumentType.RESUME, description="Type of document"),
    user_auth: tuple[int, bool] = Depends(get_requesting_user_or_id),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """Upload a career document, validate format and magic bytes, and extract plain text."""
    uid, _ = user_auth
    file_bytes = await file.read()
    filename = file.filename or "unnamed_document"
    content_type = file.content_type or "application/octet-stream"

    document = await service.upload_document(
        user_id=uid,
        filename=filename,
        content_type=content_type,
        file_bytes=file_bytes,
        doc_type=doc_type,
        process_sync=True,
    )
    return DocumentResponse.model_validate(document)


@router.get("", response_model=PaginatedResponse[DocumentResponse], summary="List uploaded documents")
async def list_documents(
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page"),
    user_auth: tuple[int, bool] = Depends(get_requesting_user_or_id),
    service: DocumentService = Depends(get_document_service),
) -> PaginatedResponse[DocumentResponse]:
    """Retrieve all uploaded documents for the requesting user."""
    uid, _ = user_auth
    params = PaginationParams(page=page, per_page=per_page)
    docs, total = await service.list_documents(user_id=uid, params=params)
    items = [DocumentResponse.model_validate(d) for d in docs]
    return PaginatedResponse.create(items=items, total=total, params=params)


@router.get("/{document_id}", response_model=DocumentResponse, summary="Get document details & extraction status")
async def get_document(
    document_id: int,
    user_auth: tuple[int, bool] = Depends(get_requesting_user_or_id),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """Retrieve document status and extracted text."""
    uid, is_admin = user_auth
    document = await service.get_document(document_id=document_id, user_id=uid, is_admin=is_admin)
    return DocumentResponse.model_validate(document)


@router.get("/{document_id}/download", summary="Download raw document file")
async def download_document(
    document_id: int,
    user_auth: tuple[int, bool] = Depends(get_requesting_user_or_id),
    service: DocumentService = Depends(get_document_service),
) -> Response:
    """Download the original uploaded document binary bytes."""
    uid, is_admin = user_auth
    file_bytes, filename, mime_type = await service.download_document(
        document_id=document_id,
        user_id=uid,
        is_admin=is_admin,
    )
    return Response(
        content=file_bytes,
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete document")
async def delete_document(
    document_id: int,
    user_auth: tuple[int, bool] = Depends(get_requesting_user_or_id),
    service: DocumentService = Depends(get_document_service),
) -> None:
    """Delete a document file and associated embeddings/chunks."""
    uid, is_admin = user_auth
    await service.delete_document(document_id=document_id, user_id=uid, is_admin=is_admin)

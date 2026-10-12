"""Pydantic schemas for Document entities."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus, DocumentType


class DocumentResponse(BaseModel):
    """Document metadata and status representation."""
    id: int
    user_id: int
    filename: str
    mime_type: str
    file_size: int
    doc_type: DocumentType
    status: DocumentStatus
    extracted_text: str | None = None
    char_count: int | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

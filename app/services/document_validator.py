"""Document upload validation: size, extension, MIME, magic bytes, and path safety."""

import os
import re

from app.core.config import get_settings
from app.core.errors import ValidationError

ALLOWED_EXTENSIONS: set[str] = {".pdf", ".docx", ".txt"}

ALLOWED_MIME_TYPES: set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

# Magic byte signatures
PDF_MAGIC = b"%PDF"
DOCX_MAGIC = b"PK\x03\x04"


def sanitize_filename(filename: str) -> str:
    """Sanitize original filename to remove path traversal and hazardous characters."""
    base = os.path.basename(filename).strip()
    # Strip any characters except alphanumerics, dots, underscores, dashes
    clean = re.sub(r"[^\w.\-]", "_", base)
    if not clean or clean.startswith("."):
        clean = f"document_{clean.lstrip('.')}"
    return clean[:200]


def validate_document(
    filename: str,
    content_type: str,
    file_bytes: bytes,
) -> tuple[str, str]:
    """
    Validates document constraints:
    1. Maximum file size
    2. Whitelisted file extensions
    3. Whitelisted MIME types
    4. Magic bytes integrity check
    Returns sanitized filename and canonical extension.
    """
    settings = get_settings()

    # 1. Size check
    file_size = len(file_bytes)
    if file_size == 0:
        raise ValidationError(message="Uploaded file is empty (0 bytes)")

    if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise ValidationError(
            message=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB",
            details={"file_size": file_size, "max_allowed": settings.MAX_UPLOAD_SIZE_BYTES},
        )

    # 2. Extension check
    safe_name = sanitize_filename(filename)
    _, ext = os.path.splitext(safe_name.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            message=f"Unsupported file extension '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            details={"extension": ext, "allowed_extensions": list(ALLOWED_EXTENSIONS)},
        )

    # 3. MIME check
    norm_content_type = content_type.lower().split(";")[0].strip()
    if norm_content_type not in ALLOWED_MIME_TYPES:
        allowed_list = ", ".join(sorted(ALLOWED_MIME_TYPES))
        raise ValidationError(
            message=f"Unsupported MIME type '{norm_content_type}'. Allowed types: {allowed_list}",
            details={"mime_type": norm_content_type},
        )

    # 4. Deep magic bytes verification
    if ext == ".pdf":
        if not file_bytes.startswith(PDF_MAGIC):
            raise ValidationError(
                message="File content does not match PDF format signature",
                details={"expected_magic": "%PDF"},
            )
    elif ext == ".docx":
        if not file_bytes.startswith(DOCX_MAGIC):
            raise ValidationError(
                message="File content does not match DOCX OpenXML zip signature",
                details={"expected_magic": "PK"},
            )
    elif ext == ".txt" and b"\x00" in file_bytes[:1024]:
        # Ensure plain text is not an executable or binary disguised as text (must not contain null bytes)
        raise ValidationError(message="Binary or executable file detected in plain text upload")

    return safe_name, ext

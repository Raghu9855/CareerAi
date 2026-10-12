"""Text extraction pipeline for PDF, DOCX, and TXT files."""

import io
import re

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.core.errors import ValidationError
from app.core.logging import get_logger

logger = get_logger("careerai.extraction")


def clean_extracted_text(text: str) -> str:
    """Normalize extracted text by stripping control characters and excessive whitespace."""
    if not text:
        return ""
    # Normalize line breaks and multiple whitespaces
    cleaned = re.sub(r"\r\n|\r", "\n", text)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from PDF bytes using pypdf."""
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        pages_text = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                pages_text.append(page_text)
        return clean_extracted_text("\n\n".join(pages_text))
    except Exception as exc:
        logger.error(f"Failed extracting text from PDF: {exc}")
        raise ValidationError(message=f"Corrupt or unreadable PDF document: {exc}") from exc


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract plain text from DOCX bytes using python-docx."""
    try:
        doc = DocxDocument(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return clean_extracted_text("\n\n".join(paragraphs))
    except Exception as exc:
        logger.error(f"Failed extracting text from DOCX: {exc}")
        raise ValidationError(message=f"Corrupt or unreadable DOCX document: {exc}") from exc


def extract_text_from_txt(file_bytes: bytes) -> str:
    """Extract plain text from TXT bytes with UTF-8 / Latin-1 fallback."""
    try:
        return clean_extracted_text(file_bytes.decode("utf-8"))
    except UnicodeDecodeError:
        try:
            return clean_extracted_text(file_bytes.decode("latin-1"))
        except Exception as exc:
            raise ValidationError(message="Unreadable text document encoding") from exc


def extract_text(file_bytes: bytes, extension: str) -> str:
    """Route document bytes to the appropriate format extractor based on extension."""
    norm_ext = extension.lower().strip()
    if norm_ext == ".pdf":
        return extract_text_from_pdf(file_bytes)
    elif norm_ext == ".docx":
        return extract_text_from_docx(file_bytes)
    elif norm_ext == ".txt":
        return extract_text_from_txt(file_bytes)
    else:
        raise ValidationError(message=f"Unsupported format for text extraction: {norm_ext}")

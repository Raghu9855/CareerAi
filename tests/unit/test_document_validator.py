"""Unit tests for document upload validator and filename sanitizer."""

import pytest

from app.core.errors import ValidationError
from app.services.document_validator import sanitize_filename, validate_document


def test_sanitize_filename() -> None:
    """Verify filename sanitization strips traversal and hazardous characters."""
    assert sanitize_filename("../../../etc/shadow") == "shadow"
    assert sanitize_filename("..\\..\\resume.pdf") == "resume.pdf"
    assert sanitize_filename(".hidden_resume.pdf") == "document_hidden_resume.pdf"
    assert sanitize_filename("my resume (v2) [final]!.pdf") == "my_resume__v2___final__.pdf"


def test_validate_document_empty_file_rejected() -> None:
    """Verify 0-byte file raises ValidationError."""
    with pytest.raises(ValidationError) as exc:
        validate_document("empty.txt", "text/plain", b"")
    assert "empty (0 bytes)" in exc.value.message


def test_validate_document_unsupported_extension_rejected() -> None:
    """Verify disallowed file extension raises ValidationError."""
    with pytest.raises(ValidationError) as exc:
        validate_document("malicious.sh", "text/plain", b"echo hello")
    assert "Unsupported file extension" in exc.value.message


def test_validate_document_unsupported_mime_rejected() -> None:
    """Verify disallowed MIME type raises ValidationError."""
    with pytest.raises(ValidationError) as exc:
        validate_document("resume.pdf", "application/x-executable", b"%PDF-1.4 valid header")
    assert "Unsupported MIME type" in exc.value.message


def test_validate_document_spoofed_pdf_magic_rejected() -> None:
    """Verify PDF with non-%PDF signature is rejected."""
    with pytest.raises(ValidationError) as exc:
        validate_document("fake.pdf", "application/pdf", b"NOT_A_PDF_STREAM")
    assert "does not match PDF format signature" in exc.value.message


def test_validate_document_spoofed_docx_magic_rejected() -> None:
    """Verify DOCX without PK zip signature is rejected."""
    with pytest.raises(ValidationError) as exc:
        validate_document(
            "fake.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            b"CORRUPT_HEADER",
        )
    assert "does not match DOCX OpenXML zip signature" in exc.value.message


def test_validate_document_binary_disguised_as_text_rejected() -> None:
    """Verify null bytes in TXT document trigger rejection."""
    with pytest.raises(ValidationError) as exc:
        validate_document("shell.txt", "text/plain", b"MZ\x90\x00\x03\x00\x00\x00BinaryExe")
    assert "Binary or executable file detected" in exc.value.message


def test_validate_document_valid_inputs() -> None:
    """Verify valid TXT, PDF, and DOCX files pass validation."""
    name, ext = validate_document("valid.txt", "text/plain", b"Valid candidate text notes.")
    assert name == "valid.txt"
    assert ext == ".txt"

    name, ext = validate_document("valid.pdf", "application/pdf", b"%PDF-1.7 standard header")
    assert name == "valid.pdf"
    assert ext == ".pdf"

    name, ext = validate_document(
        "valid.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        b"PK\x03\x04valid_stream",
    )
    assert name == "valid.docx"
    assert ext == ".docx"

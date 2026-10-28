"""Unit tests for LocalStorageBackend with path safety and error handling."""

import os
import tempfile

import pytest

from app.core.errors import NotFoundError, ValidationError
from app.services.storage.local import LocalStorageBackend


@pytest.fixture
def temp_storage():
    """Create a temporary directory for local storage testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = LocalStorageBackend(root_dir=tmpdir)
        yield backend, tmpdir


@pytest.mark.asyncio
async def test_local_save_and_get_success(temp_storage) -> None:
    """Verify storing and retrieving file content."""
    backend, tmpdir = temp_storage
    content = b"Candidate Resume Content in PDF format"
    filename = "alice_resume.pdf"

    saved_key = await backend.save(content, filename, "application/pdf")
    assert saved_key.endswith("_alice_resume.pdf")

    # File exists on disk
    file_path = os.path.join(tmpdir, saved_key)
    assert os.path.exists(file_path)

    # Retrieval
    retrieved = await backend.get(saved_key)
    assert retrieved == content


@pytest.mark.asyncio
async def test_local_get_not_found(temp_storage) -> None:
    """Verify getting a non-existent file raises NotFoundError."""
    backend, _ = temp_storage
    with pytest.raises(NotFoundError) as exc_info:
        await backend.get("non_existent_file.pdf")
    assert "Stored file not found" in exc_info.value.message


@pytest.mark.asyncio
async def test_local_exists_and_delete(temp_storage) -> None:
    """Verify exists check and file deletion."""
    backend, _ = temp_storage
    content = b"Test document"
    saved_key = await backend.save(content, "test.txt", "text/plain")

    assert await backend.exists(saved_key) is True

    deleted = await backend.delete(saved_key)
    assert deleted is True

    assert await backend.exists(saved_key) is False

    # Deleting non-existent file returns False gracefully
    assert await backend.delete("non_existent_file.txt") is False


@pytest.mark.asyncio
async def test_local_path_traversal_prevention(temp_storage) -> None:
    """Verify that path traversal attempts are detected and rejected."""
    backend, _ = temp_storage
    with pytest.raises(ValidationError) as exc_info:
        await backend.get("../../etc/passwd")
    assert "Path traversal attempt detected" in exc_info.value.message

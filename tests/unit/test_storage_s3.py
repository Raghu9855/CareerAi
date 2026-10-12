"""Unit tests for AWS S3 Storage backend with mocked boto3 client."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.errors import ExternalServiceError, NotFoundError
from app.services.storage.s3 import S3StorageBackend


@pytest.fixture
def s3_backend() -> S3StorageBackend:
    """Instantiate S3 backend configured with dummy AWS credentials."""
    return S3StorageBackend(
        bucket_name="test-careerai-bucket",
        region="us-east-1",
        access_key_id="TESTKEYID",
        secret_access_key="TESTSECRETKEY",
    )


@pytest.mark.asyncio
async def test_s3_save_success(s3_backend: S3StorageBackend) -> None:
    """Verify successful upload to S3."""
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client

    with patch.dict("sys.modules", {"boto3": mock_boto3}):
        key = await s3_backend.save(b"sample resume content", "resume.pdf", "application/pdf")
        assert key.startswith("documents/")
        assert key.endswith("_resume.pdf")
        mock_client.put_object.assert_called_once_with(
            Bucket="test-careerai-bucket",
            Key=key,
            Body=b"sample resume content",
            ContentType="application/pdf",
        )


@pytest.mark.asyncio
async def test_s3_save_failure_raises_external_service_error(s3_backend: S3StorageBackend) -> None:
    """Verify S3 upload exception maps to ExternalServiceError."""
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_client.put_object.side_effect = RuntimeError("S3 connection reset")
    mock_boto3.client.return_value = mock_client

    with patch.dict("sys.modules", {"boto3": mock_boto3}):
        with pytest.raises(ExternalServiceError) as exc_info:
            await s3_backend.save(b"data", "file.pdf", "application/pdf")
        assert "Failed to persist file to AWS S3" in exc_info.value.message


@pytest.mark.asyncio
async def test_s3_get_success(s3_backend: S3StorageBackend) -> None:
    """Verify fetching object from S3."""
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = b"retrieved file bytes"
    mock_client.get_object.return_value = {"Body": mock_body}
    mock_boto3.client.return_value = mock_client

    with patch.dict("sys.modules", {"boto3": mock_boto3}):
        content = await s3_backend.get("documents/xyz_file.pdf")
        assert content == b"retrieved file bytes"


@pytest.mark.asyncio
async def test_s3_get_failure_raises_not_found(s3_backend: S3StorageBackend) -> None:
    """Verify missing object in S3 maps to NotFoundError."""
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_client.get_object.side_effect = Exception("NoSuchKey")
    mock_boto3.client.return_value = mock_client

    with patch.dict("sys.modules", {"boto3": mock_boto3}), pytest.raises(NotFoundError):
        await s3_backend.get("documents/nonexistent.pdf")


@pytest.mark.asyncio
async def test_s3_delete_and_exists(s3_backend: S3StorageBackend) -> None:
    """Verify delete and head_object existence check."""
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client

    with patch.dict("sys.modules", {"boto3": mock_boto3}):
        # Delete success
        del_res = await s3_backend.delete("documents/file.pdf")
        assert del_res is True
        mock_client.delete_object.assert_called_once()

        # Exists success
        exists_res = await s3_backend.exists("documents/file.pdf")
        assert exists_res is True

        # Exists when head_object fails
        mock_client.head_object.side_effect = Exception("404 Not Found")
        assert await s3_backend.exists("documents/file.pdf") is False

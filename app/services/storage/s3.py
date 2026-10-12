"""AWS S3 Storage backend implementation."""

import uuid

from app.core.config import get_settings
from app.core.errors import ExternalServiceError, NotFoundError
from app.services.storage.local import LocalStorageBackend


class S3StorageBackend:
    """Cloud object storage backend for AWS S3 with transparent local fallback when unconfigured."""

    def __init__(
        self,
        bucket_name: str,
        region: str = "us-east-1",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        self.bucket_name = bucket_name
        self.region = region
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        # Fallback to local storage if AWS credentials are not configured (e.g. dev/test)
        self._fallback_local: LocalStorageBackend | None = None
        if not self.access_key_id or not self.secret_access_key:
            settings = get_settings()
            self._fallback_local = LocalStorageBackend(root_dir=settings.STORAGE_LOCAL_ROOT)

    async def save(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        """Store file in S3 bucket or local fallback."""
        if self._fallback_local:
            return await self._fallback_local.save(file_bytes, filename, content_type)

        key = f"documents/{uuid.uuid4().hex}_{filename}"
        try:
            # When boto3 is configured, upload bytes
            import boto3

            s3_client = boto3.client(
                "s3",
                region_name=self.region,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
            )
            s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_bytes,
                ContentType=content_type,
            )
            return key
        except Exception as exc:
            raise ExternalServiceError(
                message="Failed to persist file to AWS S3",
                details={"bucket": self.bucket_name, "key": key, "error": str(exc)},
            ) from exc

    async def get(self, storage_path: str) -> bytes:
        """Fetch file bytes from S3 or local fallback."""
        if self._fallback_local:
            return await self._fallback_local.get(storage_path)

        try:
            import boto3

            s3_client = boto3.client(
                "s3",
                region_name=self.region,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
            )
            response = s3_client.get_object(Bucket=self.bucket_name, Key=storage_path)
            content: bytes = response["Body"].read()
            return content
        except Exception as exc:
            raise NotFoundError(
                message="File not found in S3",
                details={"bucket": self.bucket_name, "key": storage_path, "error": str(exc)},
            ) from exc

    async def delete(self, storage_path: str) -> bool:
        """Delete object from S3 or local fallback."""
        if self._fallback_local:
            return await self._fallback_local.delete(storage_path)

        try:
            import boto3

            s3_client = boto3.client(
                "s3",
                region_name=self.region,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
            )
            s3_client.delete_object(Bucket=self.bucket_name, Key=storage_path)
            return True
        except Exception:
            return False

    async def exists(self, storage_path: str) -> bool:
        """Check if object exists in S3 or local fallback."""
        if self._fallback_local:
            return await self._fallback_local.exists(storage_path)

        try:
            import boto3

            s3_client = boto3.client(
                "s3",
                region_name=self.region,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
            )
            s3_client.head_object(Bucket=self.bucket_name, Key=storage_path)
            return True
        except Exception:
            return False

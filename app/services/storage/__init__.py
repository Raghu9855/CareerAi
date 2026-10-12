"""Storage backend factory."""

from functools import lru_cache

from app.core.config import get_settings
from app.services.storage.base import StorageBackend
from app.services.storage.local import LocalStorageBackend
from app.services.storage.s3 import S3StorageBackend


@lru_cache
def get_storage_backend() -> StorageBackend:
    """Instantiate configured storage backend (local filesystem or AWS S3)."""
    settings = get_settings()
    if settings.STORAGE_BACKEND.lower() == "s3":
        return S3StorageBackend(
            bucket_name=settings.AWS_S3_BUCKET,
            region=settings.AWS_REGION,
            access_key_id=settings.AWS_ACCESS_KEY_ID,
            secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
    return LocalStorageBackend(root_dir=settings.STORAGE_LOCAL_ROOT)


__all__ = ["StorageBackend", "LocalStorageBackend", "S3StorageBackend", "get_storage_backend"]

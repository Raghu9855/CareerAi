"""Storage backend factory."""

from functools import lru_cache

from app.core.config import get_settings
from app.services.storage.base import StorageBackend
from app.services.storage.local import LocalStorageBackend


@lru_cache
def get_storage_backend() -> StorageBackend:
    """Instantiate configured storage backend (local filesystem)."""
    settings = get_settings()
    return LocalStorageBackend(root_dir=settings.STORAGE_LOCAL_ROOT)


__all__ = ["StorageBackend", "LocalStorageBackend", "get_storage_backend"]

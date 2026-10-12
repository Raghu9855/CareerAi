"""Storage backend protocol abstraction."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Abstract interface for local or cloud file object storage."""

    async def save(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        """Persist file bytes and return storage path / key."""
        ...

    async def get(self, storage_path: str) -> bytes:
        """Retrieve stored file contents as bytes."""
        ...

    async def delete(self, storage_path: str) -> bool:
        """Delete stored file from storage."""
        ...

    async def exists(self, storage_path: str) -> bool:
        """Check if file exists in storage."""
        ...

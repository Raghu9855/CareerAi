"""Local filesystem storage backend with path traversal security defense."""

import os
import uuid

import aiofiles
import aiofiles.os

from app.core.errors import NotFoundError, ValidationError


class LocalStorageBackend:
    """Stores files on the local filesystem within an isolated root directory."""

    def __init__(self, root_dir: str) -> None:
        self.root_dir = os.path.realpath(root_dir)
        os.makedirs(self.root_dir, exist_ok=True)

    def _resolve_safe_path(self, storage_path: str) -> str:
        """Resolves target path and ensures it does not escape the configured root directory."""
        clean_path = os.path.normpath(storage_path)
        resolved = os.path.realpath(os.path.join(self.root_dir, clean_path))
        if not resolved.startswith(self.root_dir):
            raise ValidationError(
                message="Security violation: Path traversal attempt detected",
                details={"storage_path": storage_path},
            )
        return resolved

    async def save(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        """Save file with a unique secure filename."""
        safe_base = os.path.basename(filename).replace(" ", "_")
        unique_name = f"{uuid.uuid4().hex}_{safe_base}"
        target_path = self._resolve_safe_path(unique_name)

        async with aiofiles.open(target_path, "wb") as f:
            await f.write(file_bytes)

        return unique_name

    async def get(self, storage_path: str) -> bytes:
        """Read and return file bytes."""
        resolved = self._resolve_safe_path(storage_path)
        if not os.path.exists(resolved):
            raise NotFoundError(message="Stored file not found", details={"storage_path": storage_path})

        async with aiofiles.open(resolved, "rb") as f:
            content = await f.read()
            return bytes(content)

    async def delete(self, storage_path: str) -> bool:
        """Remove file from filesystem."""
        try:
            resolved = self._resolve_safe_path(storage_path)
            if os.path.exists(resolved):
                await aiofiles.os.remove(resolved)
                return True
            return False
        except Exception:
            return False

    async def exists(self, storage_path: str) -> bool:
        """Check if file exists."""
        try:
            resolved = self._resolve_safe_path(storage_path)
            return os.path.exists(resolved)
        except Exception:
            return False

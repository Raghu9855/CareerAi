"""Vector store abstraction and InMemoryVectorStore with strict multi-tenant isolation."""

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol

from app.core.logging import get_logger

logger = get_logger("careerai.ai.rag.vectorstore")


@dataclass
class VectorChunk:
    """Stored chunk vector and associated document metadata."""

    id: str
    vector: list[float]
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    # Required metadata keys: "user_id": int, "document_id": int, "chunk_index": int, "filename": str


@dataclass
class SearchResult:
    """Vector search hit with relevance similarity score."""

    chunk_id: str
    score: float
    text: str
    metadata: dict[str, Any]


class VectorStore(Protocol):
    """Protocol for vector indexing, similarity search, and tenant-safe deletion."""

    async def add_chunks(self, chunks: list[VectorChunk]) -> list[str]:
        """Index a list of vector chunks."""
        ...

    async def search(
        self,
        query_vector: list[float],
        user_id: int,
        top_k: int = 4,
        document_id: int | None = None,
        min_similarity: float = 0.2,
    ) -> list[SearchResult]:
        """Search top-K most similar chunks strictly scoped to the requesting user."""
        ...

    async def delete_by_document(self, document_id: int, user_id: int) -> int:
        """Delete all vectors for a specific document and user."""
        ...

    async def delete_by_user(self, user_id: int) -> int:
        """Delete all vectors belonging to a user."""
        ...


class InMemoryVectorStore(VectorStore):
    """Thread-safe, in-memory vector store enforcing strict tenant isolation."""

    def __init__(self) -> None:
        # id -> VectorChunk
        self._chunks: dict[str, VectorChunk] = {}

    async def add_chunks(self, chunks: list[VectorChunk]) -> list[str]:
        """Store chunks in index."""
        added_ids = []
        for chunk in chunks:
            self._chunks[chunk.id] = chunk
            added_ids.append(chunk.id)
        logger.info(f"Indexed {len(added_ids)} chunks into vector store")
        return added_ids

    async def search(
        self,
        query_vector: list[float],
        user_id: int,
        top_k: int = 4,
        document_id: int | None = None,
        min_similarity: float = 0.2,
    ) -> list[SearchResult]:
        """Search top-k chunks with strict user_id filtering."""
        if not self._chunks or not query_vector:
            return []

        q_norm = math.sqrt(sum(x * x for x in query_vector))
        if q_norm == 0.0:
            return []

        candidates: list[SearchResult] = []

        for chunk in self._chunks.values():
            # STRICT TENANT ISOLATION: Never consider chunks belonging to other users
            chunk_user_id = chunk.metadata.get("user_id")
            if chunk_user_id != user_id:
                continue

            # Optional document_id filter
            if document_id is not None and chunk.metadata.get("document_id") != document_id:
                continue

            # Compute Cosine Similarity
            dot = sum(a * b for a, b in zip(query_vector, chunk.vector, strict=False))
            c_norm = math.sqrt(sum(x * x for x in chunk.vector))
            sim = dot / (q_norm * c_norm) if c_norm > 0 else 0.0

            if sim >= min_similarity:
                candidates.append(
                    SearchResult(
                        chunk_id=chunk.id,
                        score=round(sim, 4),
                        text=chunk.text,
                        metadata=chunk.metadata,
                    )
                )

        # Sort descending by similarity score
        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates[:top_k]

    async def delete_by_document(self, document_id: int, user_id: int) -> int:
        """Remove vectors for document_id strictly owned by user_id."""
        to_delete = [
            cid
            for cid, chunk in self._chunks.items()
            if chunk.metadata.get("document_id") == document_id and chunk.metadata.get("user_id") == user_id
        ]
        for cid in to_delete:
            self._chunks.pop(cid, None)
        logger.info(f"Deleted {len(to_delete)} vectors for document {document_id}")
        return len(to_delete)

    async def delete_by_user(self, user_id: int) -> int:
        """Remove all vectors owned by user_id."""
        to_delete = [cid for cid, chunk in self._chunks.items() if chunk.metadata.get("user_id") == user_id]
        for cid in to_delete:
            self._chunks.pop(cid, None)
        return len(to_delete)

    def clear(self) -> None:
        """Clear all stored vectors (for testing)."""
        self._chunks.clear()


@lru_cache
def get_vector_store() -> VectorStore:
    """Return singleton vector store instance."""
    return InMemoryVectorStore()

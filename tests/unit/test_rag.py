"""Unit tests for RAG chunker, embedder, and in-memory vector store."""

import math

import pytest

from app.ai.rag.chunker import DocumentChunker
from app.ai.rag.embedder import MockEmbedder
from app.ai.rag.vector_store import InMemoryVectorStore, VectorChunk


def test_chunker_sliding_window_and_overlap() -> None:
    """Verify document chunker creates overlapping chunks with unique vector IDs."""
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
    sample_text = (
        "First sentence discussing Python and FastAPI. "
        "Second sentence covering MySQL and Redis caching. "
        "Third sentence detailing Docker containerization and Kubernetes. "
        "Fourth sentence describing Linux deployment pipelines."
    )
    chunks = chunker.chunk_text(sample_text, document_id=1, user_id=10)
    assert len(chunks) >= 2
    for i, c in enumerate(chunks):
        assert c.chunk_index == i
        assert c.vector_id == f"user_10_doc_1_chunk_{i}"
        assert len(c.content) > 0


@pytest.mark.asyncio
async def test_mock_embedder_dimension_and_normalization() -> None:
    """Verify mock embedder generates L2-normalized vectors."""
    embedder = MockEmbedder(dimension=128)
    vec = await embedder.embed_query("Python FastAPI microservices")
    assert len(vec) == 128
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-5


@pytest.mark.asyncio
async def test_vector_store_strict_tenant_isolation() -> None:
    """Verify vector store search strictly enforces user_id boundaries."""
    store = InMemoryVectorStore()
    user_a_id = 1
    user_b_id = 2

    # User A index
    chunk_a = VectorChunk(
        id="chunk_a",
        vector=[1.0, 0.0, 0.0],
        text="User A secret career information",
        metadata={"user_id": user_a_id, "document_id": 10},
    )
    await store.add_chunks([chunk_a])

    # User B queries identical vector direction
    query_vector = [1.0, 0.0, 0.0]
    results_user_b = await store.search(query_vector=query_vector, user_id=user_b_id, top_k=5)
    assert len(results_user_b) == 0  # User B MUST NOT see User A's data

    # User A queries
    results_user_a = await store.search(query_vector=query_vector, user_id=user_a_id, top_k=5)
    assert len(results_user_a) == 1
    assert results_user_a[0].chunk_id == "chunk_a"


@pytest.mark.asyncio
async def test_vector_store_deletion_cleanup() -> None:
    """Verify document deletion removes only targeted document vectors for that user."""
    store = InMemoryVectorStore()
    user_id = 1

    chunks = [
        VectorChunk(
            id="c1",
            vector=[1.0, 0.0],
            text="Doc 1 chunk",
            metadata={"user_id": user_id, "document_id": 100},
        ),
        VectorChunk(
            id="c2",
            vector=[0.0, 1.0],
            text="Doc 2 chunk",
            metadata={"user_id": user_id, "document_id": 200},
        ),
    ]
    await store.add_chunks(chunks)

    # Delete doc 100
    deleted_count = await store.delete_by_document(document_id=100, user_id=user_id)
    assert deleted_count == 1

    # Verify doc 100 is gone while doc 200 remains
    hits = await store.search(query_vector=[1.0, 0.0], user_id=user_id, document_id=100)
    assert len(hits) == 0

    hits_doc2 = await store.search(query_vector=[0.0, 1.0], user_id=user_id, document_id=200)
    assert len(hits_doc2) == 1

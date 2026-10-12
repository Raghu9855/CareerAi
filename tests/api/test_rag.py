"""API integration tests for Document RAG indexing, questioning, citations, and multi-tenant isolation."""

import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_rag_end_to_end_indexing_query_and_citations(client: AsyncClient) -> None:
    """Verify document upload -> RAG indexing -> semantic search with source citations."""
    # 1. Register User A
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "rag_user_a@example.com", "password": "SecurePassword123!", "full_name": "RAG User A"},
    )
    token = reg_resp.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload Document
    doc_content = (
        b"Alice Smith - Cloud Platform Architect.\n"
        b"Extensive expertise deploying microservices to AWS ECS, Kubernetes, and Terraform.\n"
        b"Architected high-scale MySQL databases and configured Redis caching clusters.\n"
        b"Earned AWS Certified Solutions Architect Professional certification."
    )
    upload_resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("alice_resume.txt", io.BytesIO(doc_content), "text/plain")},
        headers=headers,
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["id"]

    # 3. Index Document in RAG
    index_resp = await client.post(f"/api/v1/rag/index/{doc_id}", headers=headers)
    assert index_resp.status_code == 200
    assert index_resp.json()["chunks_indexed"] >= 1

    # 4. Query RAG with relevant question
    query_payload = {"question": "What cloud platforms and databases does Alice use?", "top_k": 3}
    query_resp = await client.post("/api/v1/rag/query", json=query_payload, headers=headers)
    assert query_resp.status_code == 200
    data = query_resp.json()

    assert data["has_answer"] is True
    assert data["retrieval_count"] >= 1
    assert data["confidence"] > 0.2
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["document_id"] == doc_id
    assert "alice_resume.txt" in data["citations"][0]["filename"]


@pytest.mark.asyncio
async def test_rag_empty_retrieval_rejection(client: AsyncClient) -> None:
    """Verify unanswerable queries or queries with weak relevance return 'I don't know' without false hallucinations."""
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "rag_empty_user@example.com", "password": "SecurePassword123!", "full_name": "Empty User"},
    )
    token = reg_resp.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Upload document with specific technical focus
    doc_content = b"Candidate experience: Golang backend development and gRPC microservices."
    upload_resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("golang_cv.txt", io.BytesIO(doc_content), "text/plain")},
        headers=headers,
    )
    doc_id = upload_resp.json()["id"]
    await client.post(f"/api/v1/rag/index/{doc_id}", headers=headers)

    # Query about completely unrelated topic
    unrelated_query = {"question": "What is the candidate's secret baking recipe for strawberry cheesecake?"}
    query_resp = await client.post("/api/v1/rag/query", json=unrelated_query, headers=headers)
    assert query_resp.status_code == 200
    data = query_resp.json()

    assert data["has_answer"] is False
    assert len(data["citations"]) == 0
    assert "could not find" in data["answer"].lower()


@pytest.mark.asyncio
async def test_rag_cross_user_tenant_isolation(client: AsyncClient) -> None:
    """Verify strict tenant isolation: User B cannot retrieve or reindex User A's private documents."""
    # User A
    user_a = await client.post(
        "/api/v1/auth/register",
        json={"email": "tenant_alice@example.com", "password": "SecurePassword123!", "full_name": "Alice"},
    )
    headers_a = {"Authorization": f"Bearer {user_a.json()['tokens']['access_token']}"}

    # User B
    user_b = await client.post(
        "/api/v1/auth/register",
        json={"email": "tenant_bob@example.com", "password": "SecurePassword123!", "full_name": "Bob"},
    )
    headers_b = {"Authorization": f"Bearer {user_b.json()['tokens']['access_token']}"}

    # Alice uploads and indexes sensitive compensation and career info
    alice_doc = b"CONFIDENTIAL: Alice Smith compensation details and executive promotions at MegaCorp."
    upload_resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("confidential_review.txt", io.BytesIO(alice_doc), "text/plain")},
        headers=headers_a,
    )
    alice_doc_id = upload_resp.json()["id"]
    await client.post(f"/api/v1/rag/index/{alice_doc_id}", headers=headers_a)

    # 1. Bob queries exact words from Alice's document -> must receive 0 citations & no answer
    bob_query = {"question": "What are Alice Smith's confidential compensation details at MegaCorp?"}
    bob_resp = await client.post("/api/v1/rag/query", json=bob_query, headers=headers_b)
    assert bob_resp.status_code == 200
    bob_data = bob_resp.json()

    assert bob_data["has_answer"] is False
    assert len(bob_data["citations"]) == 0
    assert bob_data["retrieval_count"] == 0

    # 2. Bob attempts to re-index Alice's document -> 404 Not Found
    reindex_resp = await client.post(f"/api/v1/rag/index/{alice_doc_id}", headers=headers_b)
    assert reindex_resp.status_code == 404

    # 3. Alice queries her own document -> receives valid citations
    alice_resp = await client.post("/api/v1/rag/query", json=bob_query, headers=headers_a)
    assert alice_resp.status_code == 200
    assert alice_resp.json()["has_answer"] is True
    assert len(alice_resp.json()["citations"]) >= 1


@pytest.mark.asyncio
async def test_rag_deletion_cleanup(client: AsyncClient) -> None:
    """Verify document deletion cleans up both vector store embeddings and chunk database records."""
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "rag_del_user@example.com", "password": "SecurePassword123!", "full_name": "Del User"},
    )
    headers = {"Authorization": f"Bearer {reg_resp.json()['tokens']['access_token']}"}

    # Upload & Index
    upload_resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("temporary_doc.txt", io.BytesIO(b"Kubernetes cluster administration handbook."), "text/plain")},
        headers=headers,
    )
    doc_id = upload_resp.json()["id"]
    await client.post(f"/api/v1/rag/index/{doc_id}", headers=headers)

    # Delete RAG vectors
    del_resp = await client.delete(f"/api/v1/rag/documents/{doc_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["vectors_deleted"] >= 1
    assert del_resp.json()["chunks_deleted"] >= 1

    # Querying after deletion must yield no hits
    query_resp = await client.post(
        "/api/v1/rag/query",
        json={"question": "What is in the Kubernetes cluster administration handbook?"},
        headers=headers,
    )
    assert query_resp.status_code == 200
    assert query_resp.json()["has_answer"] is False
    assert len(query_resp.json()["citations"]) == 0

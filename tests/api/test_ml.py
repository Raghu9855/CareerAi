"""API integration tests for ML compatibility scoring, skill gaps, and model registry endpoints."""

import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_analyze_with_raw_text(client: AsyncClient) -> None:
    """Verify ML analysis endpoint with direct raw text inputs."""
    # 1. Register and login
    user_payload = {"email": "ml_candidate1@example.com", "password": "SecurePassword123!", "full_name": "ML Candidate"}
    reg_resp = await client.post("/api/v1/auth/register", json=user_payload)
    assert reg_resp.status_code == 201
    token = reg_resp.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Analyze compatibility
    analyze_payload = {
        "resume_text": (
            "Senior Backend Developer with 6 years experience in Python, FastAPI, MySQL, Redis, Docker, and AWS."
        ),
        "job_description": (
            "Seeking Python Backend Engineer. Required: Python, FastAPI, MySQL, Redis, Docker, Kubernetes, and AWS."
        ),
    }
    resp = await client.post("/api/v1/ml/analyze", json=analyze_payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    assert data["id"] is not None
    assert 0.0 <= data["compatibility_score"] <= 100.0
    assert 0.0 <= data["skill_match_score"] <= 100.0
    assert 0.0 <= data["text_similarity_score"] <= 100.0
    assert "Python" in data["matched_skills"]
    assert "FastAPI" in data["matched_skills"]
    assert any(m["skill"] == "Kubernetes" for m in data["missing_skills"])
    assert data["model_version"] != ""
    assert data["latency_ms"] is not None


@pytest.mark.asyncio
async def test_analyze_with_document_and_job_entities(client: AsyncClient) -> None:
    """Verify ML analysis using uploaded document ID and stored job ID."""
    # 1. Register user
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "ml_doc_user@example.com", "password": "SecurePassword123!", "full_name": "Doc User"},
    )
    token = reg_resp.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Job
    job_payload = {
        "title": "Machine Learning Engineer",
        "company": "AI Innovations",
        "description": (
            "Building NLP pipelines and vector search systems with Python, Scikit-Learn, PyTorch, Docker, "
            "Kubernetes, and AWS."
        ),
    }
    job_resp = await client.post("/api/v1/jobs", json=job_payload, headers=headers)
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    # 3. Upload Resume Document
    resume_content = b"Data Scientist proficient in Python, Scikit-Learn, NumPy, Pandas, Docker, and Git."
    upload_resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("resume.txt", io.BytesIO(resume_content), "text/plain")},
        headers=headers,
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["id"]

    # 4. Analyze via entity IDs
    analyze_resp = await client.post(
        "/api/v1/ml/analyze",
        json={"job_id": job_id, "document_id": doc_id},
        headers=headers,
    )
    assert analyze_resp.status_code == 201
    data = analyze_resp.json()
    assert data["job_id"] == job_id
    assert data["document_id"] == doc_id
    assert "Python" in data["matched_skills"]
    assert "Docker" in data["matched_skills"]
    assert "Scikit-Learn" in data["matched_skills"]


@pytest.mark.asyncio
async def test_analyze_validation_errors(client: AsyncClient) -> None:
    """Verify validation rejects requests lacking either candidate or job sources."""
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "ml_val_user@example.com", "password": "SecurePassword123!", "full_name": "Val User"},
    )
    token = reg_resp.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Missing candidate source
    resp1 = await client.post(
        "/api/v1/ml/analyze",
        json={"job_description": "We need Python developers"},
        headers=headers,
    )
    assert resp1.status_code == 422

    # Missing job source
    resp2 = await client.post(
        "/api/v1/ml/analyze",
        json={"resume_text": "I am a Python developer"},
        headers=headers,
    )
    assert resp2.status_code == 422


@pytest.mark.asyncio
async def test_cross_user_isolation_for_documents_and_analyses(client: AsyncClient) -> None:
    """Verify strict tenant isolation: users cannot analyze another user's document or view their analyses."""
    # Register User A
    user_a = await client.post(
        "/api/v1/auth/register",
        json={"email": "tenant_a_ml@example.com", "password": "SecurePassword123!", "full_name": "Tenant A"},
    )
    token_a = user_a.json()["tokens"]["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Register User B
    user_b = await client.post(
        "/api/v1/auth/register",
        json={"email": "tenant_b_ml@example.com", "password": "SecurePassword123!", "full_name": "Tenant B"},
    )
    token_b = user_b.json()["tokens"]["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A uploads document
    upload_resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("tenant_a_resume.txt", io.BytesIO(b"Python developer resume"), "text/plain")},
        headers=headers_a,
    )
    doc_a_id = upload_resp.json()["id"]

    # User B attempts to analyze using User A's private document_id -> 404
    hacked_analysis = await client.post(
        "/api/v1/ml/analyze",
        json={"document_id": doc_a_id, "job_description": "Python job requirements"},
        headers=headers_b,
    )
    assert hacked_analysis.status_code == 404

    # User A runs valid analysis
    valid_resp = await client.post(
        "/api/v1/ml/analyze",
        json={"document_id": doc_a_id, "job_description": "Python job requirements"},
        headers=headers_a,
    )
    assert valid_resp.status_code == 201
    analysis_id = valid_resp.json()["id"]

    # User B attempts to read User A's analysis record -> 404
    cross_read = await client.get(f"/api/v1/ml/analyses/{analysis_id}", headers=headers_b)
    assert cross_read.status_code == 404

    # User A can read their own analysis
    own_read = await client.get(f"/api/v1/ml/analyses/{analysis_id}", headers=headers_a)
    assert own_read.status_code == 200
    assert own_read.json()["id"] == analysis_id


@pytest.mark.asyncio
async def test_get_model_info_endpoint(client: AsyncClient) -> None:
    """Verify /api/v1/ml/model returns metadata, features, metrics, and limitations."""
    resp = await client.get("/api/v1/ml/model")
    assert resp.status_code == 200
    data = resp.json()
    assert "model_name" in data
    assert "model_version" in data
    assert "features" in data
    assert "limitations" in data
    assert len(data["limitations"]) >= 1

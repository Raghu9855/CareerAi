"""API integration tests for LLM explanations, interview prep, and graceful degradation."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.ai.llm.mock import MockLLMClient


@pytest.mark.asyncio
async def test_explain_analysis_happy_path_and_caching(client: AsyncClient) -> None:
    """Verify structured LLM explanation generation and subsequent cached responses."""
    # 1. Register & login
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "ai_user1@example.com", "password": "SecurePassword123!", "full_name": "AI User One"},
    )
    token = reg_resp.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Run ML Analysis
    analysis_resp = await client.post(
        "/api/v1/ml/analyze",
        json={
            "resume_text": "Experienced Python Engineer with FastAPI, Docker, and MySQL.",
            "job_description": "Senior Python Engineer required. FastAPI, Docker, MySQL, Redis, and Kubernetes.",
        },
        headers=headers,
    )
    assert analysis_resp.status_code == 201
    analysis_id = analysis_resp.json()["id"]

    # 3. Request LLM explanation
    explain_resp = await client.post(f"/api/v1/ai/explain/{analysis_id}", headers=headers)
    assert explain_resp.status_code == 200
    data = explain_resp.json()

    assert data["analysis_id"] == analysis_id
    assert data["degraded"] is False
    assert data["explanation_status"] == "available"
    assert data["explanation"] is not None
    assert len(data["explanation"]["strengths"]) >= 1
    assert len(data["explanation"]["areas_for_growth"]) >= 1
    assert data["explanation"]["match_verdict"] != ""

    # 4. Second call should return cached status
    cache_resp = await client.post(f"/api/v1/ai/explain/{analysis_id}", headers=headers)
    assert cache_resp.status_code == 200
    cache_data = cache_resp.json()
    assert cache_data["explanation_status"] == "cached"
    assert cache_data["degraded"] is False


@pytest.mark.asyncio
async def test_interview_prep_happy_path(client: AsyncClient) -> None:
    """Verify tailored interview question generation."""
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "ai_prep_user@example.com", "password": "SecurePassword123!", "full_name": "Prep User"},
    )
    token = reg_resp.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Run ML analysis
    analysis_resp = await client.post(
        "/api/v1/ml/analyze",
        json={
            "resume_text": "Frontend developer with React and TypeScript.",
            "job_description": "Full Stack Engineer with React, TypeScript, Python, and PostgreSQL.",
        },
        headers=headers,
    )
    analysis_id = analysis_resp.json()["id"]

    # Request interview prep
    prep_resp = await client.post(f"/api/v1/ai/interview-prep/{analysis_id}", headers=headers)
    assert prep_resp.status_code == 200
    data = prep_resp.json()

    assert data["interview_prep"] is not None
    assert len(data["interview_prep"]["technical_questions"]) >= 1
    assert len(data["interview_prep"]["behavioral_questions"]) >= 1
    assert len(data["interview_prep"]["preparation_tips"]) >= 1


@pytest.mark.asyncio
async def test_ai_graceful_degradation_on_timeout(client: AsyncClient) -> None:
    """Verify that when the LLM times out, the endpoint degrades gracefully rather than failing with 500."""
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "ai_timeout_user@example.com", "password": "SecurePassword123!", "full_name": "Timeout User"},
    )
    token = reg_resp.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    analysis_resp = await client.post(
        "/api/v1/ml/analyze",
        json={"resume_text": "Python Developer", "job_description": "Python Backend Engineer"},
        headers=headers,
    )
    analysis_id = analysis_resp.json()["id"]

    # Patch LLM client with timeout fault injection
    faulty_client = MockLLMClient(simulate_timeout=True)
    with patch("app.services.ai_service.get_llm_client", return_value=faulty_client):
        resp = await client.post(f"/api/v1/ai/explain/{analysis_id}", headers=headers)
        assert resp.status_code == 200  # Must NOT be 500
        data = resp.json()
        assert data["degraded"] is True
        assert data["explanation_status"] == "unavailable"
        assert data["explanation"] is None
        assert data["compatibility_score"] > 0


@pytest.mark.asyncio
async def test_ai_graceful_degradation_on_rate_limit(client: AsyncClient) -> None:
    """Verify graceful degradation when the LLM provider rate limits."""
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "ai_rl_user@example.com", "password": "SecurePassword123!", "full_name": "RL User"},
    )
    token = reg_resp.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    analysis_resp = await client.post(
        "/api/v1/ml/analyze",
        json={"resume_text": "Python Developer", "job_description": "Python Backend Engineer"},
        headers=headers,
    )
    analysis_id = analysis_resp.json()["id"]

    faulty_client = MockLLMClient(simulate_rate_limit=True)
    with patch("app.services.ai_service.get_llm_client", return_value=faulty_client):
        resp = await client.post(f"/api/v1/ai/explain/{analysis_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["degraded"] is True
        assert data["explanation_status"] == "unavailable"


@pytest.mark.asyncio
async def test_ai_graceful_degradation_on_malformed_json(client: AsyncClient) -> None:
    """Verify graceful degradation when the LLM returns invalid JSON."""
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ai_malformed_user@example.com",
            "password": "SecurePassword123!",
            "full_name": "Malformed User",
        },
    )
    token = reg_resp.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    analysis_resp = await client.post(
        "/api/v1/ml/analyze",
        json={"resume_text": "Python Developer", "job_description": "Python Backend Engineer"},
        headers=headers,
    )
    analysis_id = analysis_resp.json()["id"]

    faulty_client = MockLLMClient(simulate_malformed_json=True)
    with patch("app.services.ai_service.get_llm_client", return_value=faulty_client):
        resp = await client.post(f"/api/v1/ai/explain/{analysis_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["degraded"] is True
        assert data["explanation_status"] == "unavailable"


@pytest.mark.asyncio
async def test_ai_cross_user_isolation(client: AsyncClient) -> None:
    """Verify User B cannot access or generate explanations for User A's analysis record."""
    # User A
    user_a = await client.post(
        "/api/v1/auth/register",
        json={"email": "tenant_a_ai@example.com", "password": "SecurePassword123!", "full_name": "Tenant A"},
    )
    headers_a = {"Authorization": f"Bearer {user_a.json()['tokens']['access_token']}"}

    # User B
    user_b = await client.post(
        "/api/v1/auth/register",
        json={"email": "tenant_b_ai@example.com", "password": "SecurePassword123!", "full_name": "Tenant B"},
    )
    headers_b = {"Authorization": f"Bearer {user_b.json()['tokens']['access_token']}"}

    analysis_resp = await client.post(
        "/api/v1/ml/analyze",
        json={"resume_text": "Python Dev", "job_description": "Backend Role"},
        headers=headers_a,
    )
    analysis_id = analysis_resp.json()["id"]

    # User B attempts to access User A's analysis -> 404
    hacked_explain = await client.post(f"/api/v1/ai/explain/{analysis_id}", headers=headers_b)
    assert hacked_explain.status_code == 404

    hacked_prep = await client.post(f"/api/v1/ai/interview-prep/{analysis_id}", headers=headers_b)
    assert hacked_prep.status_code == 404


@pytest.mark.asyncio
async def test_get_ai_status_endpoint(client: AsyncClient) -> None:
    """Verify AI status endpoint reports active provider and model metadata."""
    resp = await client.get("/api/v1/ai/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "provider" in data
    assert "provider_label" in data
    assert "model" in data
    assert "base_url" in data
    assert "is_mock" in data

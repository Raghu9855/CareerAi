"""API integration tests for Job postings and multi-field search endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_job_lifecycle_and_validation(client: AsyncClient) -> None:
    """Verifies job creation, invalid salary validation, querying, and updating."""
    # Invalid salary (min > max) returns 422
    invalid_job = {
        "title": "Backend Engineer",
        "company": "Tech Corp",
        "description": "Building microservices with Python and FastAPI.",
        "salary_min": 180000.0,
        "salary_max": 120000.0,
    }
    err_res = await client.post("/api/v1/jobs", json=invalid_job)
    assert err_res.status_code == 422
    assert err_res.json()["error"]["code"] == "VALIDATION_ERROR"

    # Valid job creation
    valid_job = {
        "title": "Senior AI Infrastructure Engineer",
        "company": "OpenScale Labs",
        "description": "Architect high-performance distributed LLM serving systems and vector databases.",
        "location": "San Francisco, CA",
        "job_type": "full_time",
        "status": "open",
        "salary_min": 170000.0,
        "salary_max": 230000.0,
        "currency": "USD",
    }
    create_res = await client.post("/api/v1/jobs", json=valid_job)
    assert create_res.status_code == 201
    job = create_res.json()
    assert job["title"] == "Senior AI Infrastructure Engineer"
    assert job["company"] == "OpenScale Labs"

    # Search jobs by keyword
    search_res = await client.get("/api/v1/jobs?search=Infrastructure")
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert len(search_data["items"]) >= 1
    assert search_data["items"][0]["id"] == job["id"]

    # Filter jobs by location
    loc_res = await client.get("/api/v1/jobs?location=San Francisco")
    assert loc_res.status_code == 200
    assert len(loc_res.json()["items"]) >= 1

    # Filter jobs with no matches
    empty_res = await client.get("/api/v1/jobs?search=AstronautNonExistentRole")
    assert empty_res.status_code == 200
    assert len(empty_res.json()["items"]) == 0

    # Update job
    update_res = await client.put(f"/api/v1/jobs/{job['id']}", json={"location": "Remote"})
    assert update_res.status_code == 200
    assert update_res.json()["location"] == "Remote"

    # Delete job
    del_res = await client.delete(f"/api/v1/jobs/{job['id']}")
    assert del_res.status_code == 204

    # Deleted job no longer found
    get_res = await client.get(f"/api/v1/jobs/{job['id']}")
    assert get_res.status_code == 404

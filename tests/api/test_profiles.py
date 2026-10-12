"""API integration tests for Profile CRUD endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_profile_lifecycle(client: AsyncClient) -> None:
    """Verifies creating, getting, and updating a user profile."""
    # Create user first
    user = (
        await client.post(
            "/api/v1/users",
            json={
                "email": "engineer@example.com",
                "password": "Password123!",
                "full_name": "Dev Engineer",
            },
        )
    ).json()

    # Get non-existent profile returns 404
    get_res = await client.get(f"/api/v1/profiles/{user['id']}")
    assert get_res.status_code == 404

    # Create profile
    profile_payload = {
        "headline": "Senior Python Backend & AI Engineer",
        "summary": "Specialized in scalable distributed systems and LLM pipelines.",
        "location": "San Francisco, CA",
        "years_of_experience": 7.5,
        "linkedin_url": "https://linkedin.com/in/devengineer",
        "github_url": "https://github.com/devengineer",
    }
    create_res = await client.post(f"/api/v1/profiles/{user['id']}", json=profile_payload)
    assert create_res.status_code == 201
    created_profile = create_res.json()
    assert created_profile["user_id"] == user["id"]
    assert created_profile["headline"] == "Senior Python Backend & AI Engineer"
    assert created_profile["years_of_experience"] == 7.5

    # Update profile
    update_res = await client.put(
        f"/api/v1/profiles/{user['id']}",
        json={"headline": "Staff AI Platform Engineer", "years_of_experience": 8.0},
    )
    assert update_res.status_code == 200
    assert update_res.json()["headline"] == "Staff AI Platform Engineer"
    assert update_res.json()["years_of_experience"] == 8.0

    # Retrieve profile
    fetch_res = await client.get(f"/api/v1/profiles/{user['id']}")
    assert fetch_res.status_code == 200
    assert fetch_res.json()["headline"] == "Staff AI Platform Engineer"

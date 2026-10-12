"""API integration tests for Skills taxonomy and User Skills endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_skills_taxonomy_and_user_assignment(client: AsyncClient) -> None:
    """Verifies creating taxonomy skills, assigning to user, updating proficiency, and deletion."""
    # 1. Create skill in taxonomy
    skill_res = await client.post("/api/v1/skills", json={"name": "FastAPI", "category": "Frameworks"})
    assert skill_res.status_code == 201
    skill = skill_res.json()
    assert skill["name"] == "FastAPI"
    assert skill["category"] == "Frameworks"

    # Duplicate skill returns 409
    dup_res = await client.post("/api/v1/skills", json={"name": "FastAPI", "category": "Frameworks"})
    assert dup_res.status_code == 409

    # 2. List taxonomy skills
    list_res = await client.get("/api/v1/skills?category=Frameworks")
    assert list_res.status_code == 200
    assert len(list_res.json()["items"]) >= 1

    # 3. Create user
    user = (
        await client.post(
            "/api/v1/users",
            json={"email": "coder@example.com", "password": "Password123!", "full_name": "Coder"},
        )
    ).json()

    # 4. Attach skill to user profile
    attach_res = await client.post(
        f"/api/v1/skills/users/{user['id']}",
        json={"skill_id": skill["id"], "proficiency": "expert", "years_of_experience": 4.0},
    )
    assert attach_res.status_code == 201
    user_skill = attach_res.json()
    assert user_skill["proficiency"] == "expert"
    assert user_skill["years_of_experience"] == 4.0

    # 5. Duplicate skill assignment returns 409
    dup_attach = await client.post(
        f"/api/v1/skills/users/{user['id']}",
        json={"skill_id": skill["id"], "proficiency": "intermediate"},
    )
    assert dup_attach.status_code == 409

    # 6. List user skills
    user_skills_res = await client.get(f"/api/v1/skills/users/{user['id']}")
    assert user_skills_res.status_code == 200
    assert len(user_skills_res.json()) == 1

    # 7. Update user skill
    update_skill_res = await client.put(
        f"/api/v1/skills/users/{user['id']}/{skill['id']}",
        json={"years_of_experience": 5.0},
    )
    assert update_skill_res.status_code == 200
    assert update_skill_res.json()["years_of_experience"] == 5.0

    # 8. Delete user skill
    del_res = await client.delete(f"/api/v1/skills/users/{user['id']}/{skill['id']}")
    assert del_res.status_code == 204

    # Verify deleted
    empty_res = await client.get(f"/api/v1/skills/users/{user['id']}")
    assert empty_res.status_code == 200
    assert len(empty_res.json()) == 0

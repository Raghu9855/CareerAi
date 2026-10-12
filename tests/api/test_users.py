"""API integration tests for User CRUD endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_user_success(client: AsyncClient) -> None:
    """Verifies successful user registration."""
    payload = {
        "email": "sarah.connor@example.com",
        "password": "SecurePassword123!",
        "full_name": "Sarah Connor",
        "role": "user",
    }
    response = await client.post("/api/v1/users", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "sarah.connor@example.com"
    assert data["full_name"] == "Sarah Connor"
    assert data["role"] == "user"
    assert "id" in data
    assert "password" not in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_create_user_duplicate_email(client: AsyncClient) -> None:
    """Verifies that duplicate email registration returns 409 Conflict."""
    payload = {
        "email": "duplicate@example.com",
        "password": "SecurePassword123!",
        "full_name": "John Doe",
    }
    res1 = await client.post("/api/v1/users", json=payload)
    assert res1.status_code == 201

    res2 = await client.post("/api/v1/users", json=payload)
    assert res2.status_code == 409
    error = res2.json()
    assert error["success"] is False
    assert error["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_get_user_by_id(client: AsyncClient) -> None:
    """Verifies fetching user by ID."""
    created = (
        await client.post(
            "/api/v1/users",
            json={
                "email": "fetch.me@example.com",
                "password": "Password123!",
                "full_name": "Fetch Me",
            },
        )
    ).json()

    response = await client.get(f"/api/v1/users/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["email"] == "fetch.me@example.com"


@pytest.mark.asyncio
async def test_get_user_not_found(client: AsyncClient) -> None:
    """Verifies 404 response for nonexistent user."""
    response = await client.get("/api/v1/users/999999")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_list_users_paginated(client: AsyncClient) -> None:
    """Verifies pagination on users list."""
    for i in range(5):
        await client.post(
            "/api/v1/users",
            json={
                "email": f"user{i}@example.com",
                "password": "Password123!",
                "full_name": f"User {i}",
            },
        )

    response = await client.get("/api/v1/users?page=1&per_page=3")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["per_page"] == 3
    assert data["page"] == 1
    assert data["total"] >= 5


@pytest.mark.asyncio
async def test_update_user(client: AsyncClient) -> None:
    """Verifies updating user attributes."""
    created = (
        await client.post(
            "/api/v1/users",
            json={
                "email": "to.update@example.com",
                "password": "Password123!",
                "full_name": "Old Name",
            },
        )
    ).json()

    response = await client.put(f"/api/v1/users/{created['id']}", json={"full_name": "New Name"})
    assert response.status_code == 200
    assert response.json()["full_name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_user(client: AsyncClient) -> None:
    """Verifies soft-deleting a user account."""
    created = (
        await client.post(
            "/api/v1/users",
            json={
                "email": "to.delete@example.com",
                "password": "Password123!",
                "full_name": "Delete Me",
            },
        )
    ).json()

    delete_res = await client.delete(f"/api/v1/users/{created['id']}")
    assert delete_res.status_code == 204

    # Deleted user should no longer be found
    get_res = await client.get(f"/api/v1/users/{created['id']}")
    assert get_res.status_code == 404

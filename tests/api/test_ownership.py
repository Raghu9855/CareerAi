"""API integration tests verifying cross-user tenant isolation and role-based authorization."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cross_user_isolation_with_bearer_tokens(client: AsyncClient) -> None:
    """Verifies that authenticated User B cannot read, update, or delete User A's data."""
    # 1. Register User A (Alice)
    alice_res = await client.post(
        "/api/v1/auth/register",
        json={"email": "alice_tenant@example.com", "password": "Password123!", "full_name": "Alice Tenant"},
    )
    alice_tokens = alice_res.json()["tokens"]
    alice_token = alice_tokens["access_token"]
    alice_id = alice_res.json()["user"]["id"]

    # 2. Register User B (Bob)
    bob_res = await client.post(
        "/api/v1/auth/register",
        json={"email": "bob_tenant@example.com", "password": "Password123!", "full_name": "Bob Tenant"},
    )
    bob_tokens = bob_res.json()["tokens"]
    bob_token = bob_tokens["access_token"]

    # 3. Create open job
    job = (
        await client.post(
            "/api/v1/jobs",
            json={
                "title": "Principal Architect",
                "company": "Enterprise Global",
                "description": "Architecting multi-tenant cloud systems.",
                "status": "open",
            },
        )
    ).json()

    # 4. Alice applies to the job using her bearer token
    alice_app_res = await client.post(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {alice_token}"},
        json={"job_id": job["id"], "notes": "Alice's private application notes"},
    )
    assert alice_app_res.status_code == 201
    app_id = alice_app_res.json()["id"]

    # 5. Bob attempts to GET Alice's application with Bob's Bearer token -> 403 Forbidden
    bob_get_res = await client.get(
        f"/api/v1/applications/{app_id}",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert bob_get_res.status_code == 403
    assert bob_get_res.json()["error"]["code"] == "FORBIDDEN"

    # 6. Bob attempts to UPDATE Alice's application -> 403 Forbidden
    bob_put_res = await client.put(
        f"/api/v1/applications/{app_id}",
        headers={"Authorization": f"Bearer {bob_token}"},
        json={"status": "rejected"},
    )
    assert bob_put_res.status_code == 403

    # 7. Bob attempts to DELETE Alice's application -> 403 Forbidden
    bob_del_res = await client.delete(
        f"/api/v1/applications/{app_id}",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert bob_del_res.status_code == 403

    # 8. Alice successfully reads her own application
    alice_get_res = await client.get(
        f"/api/v1/applications/{app_id}",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert alice_get_res.status_code == 200
    assert alice_get_res.json()["user_id"] == alice_id


@pytest.mark.asyncio
async def test_admin_role_access(client: AsyncClient) -> None:
    """Verifies that an admin user can inspect cross-tenant records."""
    from app.core.security import create_access_token

    # 1. Register regular user
    user_res = await client.post(
        "/api/v1/auth/register",
        json={"email": "employee@example.com", "password": "Password123!", "full_name": "Employee"},
    )
    user_token = user_res.json()["tokens"]["access_token"]
    user_id = user_res.json()["user"]["id"]

    # 2. Create job and apply
    job = (
        await client.post(
            "/api/v1/jobs",
            json={"title": "Data Scientist", "company": "AI Lab", "description": "Machine learning research."},
        )
    ).json()

    app_res = await client.post(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"job_id": job["id"]},
    )
    app_id = app_res.json()["id"]

    # 3. Create Admin user & token
    admin_res = (
        await client.post(
            "/api/v1/users",
            json={"email": "admin@example.com", "password": "AdminPassword123!", "full_name": "Admin", "role": "admin"},
        )
    ).json()
    admin_token = create_access_token(subject=admin_res["id"], role="admin")

    # 4. Admin accesses employee's application -> 200 OK
    admin_get_res = await client.get(
        f"/api/v1/applications/{app_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_get_res.status_code == 200
    assert admin_get_res.json()["user_id"] == user_id

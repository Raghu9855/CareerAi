"""API integration tests for Application pipeline and ownership enforcement."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_application_lifecycle_and_ownership(client: AsyncClient) -> None:
    """Verifies applying to jobs, status updates, withdrawal, and cross-user isolation."""
    # 1. Create two users (Alice and Bob)
    alice = (
        await client.post(
            "/api/v1/users",
            json={"email": "alice@example.com", "password": "Password123!", "full_name": "Alice"},
        )
    ).json()

    bob = (
        await client.post(
            "/api/v1/users",
            json={"email": "bob@example.com", "password": "Password123!", "full_name": "Bob"},
        )
    ).json()

    # 2. Create an open job and a closed job
    open_job = (
        await client.post(
            "/api/v1/jobs",
            json={
                "title": "Platform Engineer",
                "company": "CloudNative Inc",
                "description": "Kubernetes and Python backend microservices engineering.",
                "status": "open",
            },
        )
    ).json()

    closed_job = (
        await client.post(
            "/api/v1/jobs",
            json={
                "title": "Archived Position",
                "company": "Old Corp",
                "description": "Historical position that is no longer accepting applications.",
                "status": "closed",
            },
        )
    ).json()

    # 3. Applying to closed job returns 422 validation error
    closed_apply_res = await client.post(
        f"/api/v1/applications?user_id={alice['id']}",
        json={"job_id": closed_job["id"]},
    )
    assert closed_apply_res.status_code == 422
    assert closed_apply_res.json()["error"]["code"] == "VALIDATION_ERROR"

    # 4. Alice applies to open job
    apply_res = await client.post(
        f"/api/v1/applications?user_id={alice['id']}",
        json={"job_id": open_job["id"], "notes": "Excited about Kubernetes architecture!"},
    )
    assert apply_res.status_code == 201
    application = apply_res.json()
    assert application["user_id"] == alice["id"]
    assert application["job_id"] == open_job["id"]
    assert application["status"] == "applied"

    # 5. Duplicate application by Alice returns 409 Conflict
    dup_res = await client.post(
        f"/api/v1/applications?user_id={alice['id']}",
        json={"job_id": open_job["id"]},
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["error"]["code"] == "CONFLICT"

    # 6. Cross-user isolation: Bob attempts to read Alice's application -> 403 Forbidden
    cross_user_res = await client.get(f"/api/v1/applications/{application['id']}?user_id={bob['id']}")
    assert cross_user_res.status_code == 403
    assert cross_user_res.json()["error"]["code"] == "FORBIDDEN"

    # 7. Alice reads her application -> 200 OK
    alice_read_res = await client.get(f"/api/v1/applications/{application['id']}?user_id={alice['id']}")
    assert alice_read_res.status_code == 200
    assert alice_read_res.json()["id"] == application["id"]

    # 8. Update application status
    update_res = await client.put(
        f"/api/v1/applications/{application['id']}?user_id={alice['id']}",
        json={"status": "interviewing", "notes": "Screening call scheduled for Monday."},
    )
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "interviewing"

    # 9. Withdraw application
    withdraw_res = await client.post(f"/api/v1/applications/{application['id']}/withdraw?user_id={alice['id']}")
    assert withdraw_res.status_code == 200
    assert withdraw_res.json()["status"] == "withdrawn"

    # 10. Delete application
    del_res = await client.delete(f"/api/v1/applications/{application['id']}?user_id={alice['id']}")
    assert del_res.status_code == 204

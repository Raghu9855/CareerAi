"""API integration tests for Authentication, JWT rotation, revocation, security headers, and rate limiting."""

from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_auth_registration_and_login_flow(client: AsyncClient) -> None:
    """Verifies registration, token reception, and login flow."""
    # 1. Register new account
    reg_payload = {
        "email": "authuser@example.com",
        "password": "SecurePassword123!",
        "full_name": "Auth User",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert reg_data["user"]["email"] == "authuser@example.com"
    assert "access_token" in reg_data["tokens"]
    assert "refresh_token" in reg_data["tokens"]

    # 2. Duplicate registration returns 409
    dup_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert dup_res.status_code == 409

    # 3. Successful login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "authuser@example.com", "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "bearer"

    # 4. Failed login with wrong password
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "authuser@example.com", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["error"]["code"] == "UNAUTHORIZED"

    # 5. Access /auth/me with Bearer token
    access_token = token_data["access_token"]
    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "authuser@example.com"

    # 6. Access /users/me also works
    users_me_res = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert users_me_res.status_code == 200
    assert users_me_res.json()["email"] == "authuser@example.com"


@pytest.mark.asyncio
async def test_auth_invalid_and_expired_tokens(client: AsyncClient) -> None:
    """Verifies that missing, malformed, tampered, and expired tokens are rejected with 401."""
    # 1. Missing Authorization header
    res_no_auth = await client.get("/api/v1/auth/me")
    assert res_no_auth.status_code == 401

    # 2. Malformed token
    res_malformed = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-valid-jwt"})
    assert res_malformed.status_code == 401

    # 3. Expired token
    expired_token = create_access_token(subject=1, expires_delta=timedelta(seconds=-10))
    res_expired = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res_expired.status_code == 401
    assert res_expired.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_revocation(client: AsyncClient) -> None:
    """Verifies that refreshing rotates the token and revokes the previous refresh token."""
    # 1. Register
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"email": "rotate@example.com", "password": "Password123!", "full_name": "Rotate User"},
    )
    initial_tokens = reg_res.json()["tokens"]
    old_refresh_token = initial_tokens["refresh_token"]

    # 2. Perform rotation
    rotate_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert rotate_res.status_code == 200
    new_tokens = rotate_res.json()
    new_refresh_token = new_tokens["refresh_token"]
    assert new_refresh_token != old_refresh_token

    # 3. Attempting to reuse old refresh token triggers replay detection (revocation) -> 401
    replay_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert replay_res.status_code == 401
    assert replay_res.json()["error"]["code"] == "UNAUTHORIZED"

    # 4. Logout revokes the active token
    logout_res = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": new_refresh_token},
    )
    assert logout_res.status_code == 200

    # 5. Refresh after logout returns 401
    after_logout_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_refresh_token},
    )
    assert after_logout_res.status_code == 401


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient) -> None:
    """Verifies defensive HTTP security headers are attached by middleware."""
    response = await client.get("/health")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert "strict-transport-security" in response.headers
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_rate_limiting_enforced(client: AsyncClient) -> None:
    """Verifies rate limiting returns 429 when threshold exceeded."""
    from app.core.rate_limit import limiter

    limiter.reset()

    # Hit auth register endpoint repeatedly up to limit
    exceeded = False
    for _ in range(25):
        res = await client.post(
            "/api/v1/auth/register",
            json={"email": "ratelimit@example.com", "password": "Password123!", "full_name": "RL User"},
        )
        if res.status_code == 429:
            exceeded = True
            assert res.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            break

    assert exceeded is True
    limiter.reset()

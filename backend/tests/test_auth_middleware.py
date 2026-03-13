"""Tests for the auth middleware — mock tokens, real token rejection, role checks, public paths."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestPublicPaths:
    """Public endpoints should not require auth."""

    async def test_health_check_no_auth(self, client_no_auth: AsyncClient):
        resp = await client_no_auth.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
class TestMockAuth:
    """Mock token authentication when MOCK_AUTH_ENABLED=true."""

    async def test_admin_token_accepted(self, client: AsyncClient, seed_regulation):
        resp = await client.get("/regulations")
        assert resp.status_code == 200

    async def test_missing_auth_header_returns_401(self, client_no_auth: AsyncClient):
        resp = await client_no_auth.get("/regulations")
        assert resp.status_code == 401
        assert "Missing or invalid" in resp.json()["detail"]

    async def test_invalid_token_returns_401(self, app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac.headers["Authorization"] = "Bearer totally-invalid-token"
            resp = await ac.get("/regulations")
            assert resp.status_code == 401

    async def test_no_bearer_prefix_returns_401(self, app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac.headers["Authorization"] = "Basic some-token"
            resp = await ac.get("/regulations")
            assert resp.status_code == 401


@pytest.mark.asyncio
class TestRoleChecks:
    """Role-based access control via require_role dependency."""

    async def test_admin_can_access_admin_endpoints(self, client: AsyncClient):
        """Internal admin should be able to access /admin/diagnostics."""
        resp = await client.get("/admin/diagnostics")
        assert resp.status_code == 200

    async def test_client_user_cannot_access_admin_endpoints(self, client_user: AsyncClient):
        """Client user should get 403 on admin-only endpoints."""
        resp = await client_user.get("/admin/urls")
        assert resp.status_code == 403
        assert "Not enough permissions" in resp.json()["detail"]

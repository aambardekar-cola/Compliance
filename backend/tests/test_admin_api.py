"""Tests for admin API — URL CRUD, diagnostics, pipeline logs, role checks."""
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestUrlCrud:
    """Admin URL management endpoints (CRUD)."""

    async def test_list_urls_empty(self, client: AsyncClient):
        resp = await client.get("/admin/urls")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_url(self, client: AsyncClient):
        resp = await client.post("/admin/urls", json={
            "name": "Test URL",
            "url": "https://example.com/test",
            "description": "A test compliance URL",
            "is_active": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test URL"
        assert data["url"] == "https://example.com/test"
        assert "id" in data

    async def test_create_and_list_url(self, client: AsyncClient):
        # Create
        await client.post("/admin/urls", json={
            "name": "Listed URL",
            "url": "https://example.com/listed",
        })
        # List
        resp = await client.get("/admin/urls")
        assert resp.status_code == 200
        urls = resp.json()
        assert any(u["name"] == "Listed URL" for u in urls)

    async def test_update_url(self, client: AsyncClient, seed_url):
        resp = await client.put(f"/admin/urls/{seed_url.id}", json={
            "name": "Updated Name",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"

    async def test_update_nonexistent_url_returns_404(self, client: AsyncClient):
        resp = await client.put(f"/admin/urls/{uuid.uuid4()}", json={"name": "X"})
        assert resp.status_code == 404

    async def test_delete_url(self, client: AsyncClient, seed_url):
        resp = await client.delete(f"/admin/urls/{seed_url.id}")
        assert resp.status_code == 204

    async def test_delete_nonexistent_url_returns_404(self, client: AsyncClient):
        resp = await client.delete(f"/admin/urls/{uuid.uuid4()}")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestDiagnostics:
    """GET /admin/diagnostics — pipeline status."""

    async def test_diagnostics_returns_counts(self, client: AsyncClient):
        resp = await client.get("/admin/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert "counts" in data
        assert "scraped_content" in data["counts"]
        assert "regulations" in data["counts"]
        assert "compliance_gaps" in data["counts"]

    async def test_diagnostics_with_data(self, client: AsyncClient, seed_regulation, seed_gaps):
        resp = await client.get("/admin/diagnostics")
        data = resp.json()
        assert data["counts"]["regulations"] >= 1
        assert data["counts"]["compliance_gaps"] >= 1


@pytest.mark.asyncio
class TestPipelineLogs:
    """GET /admin/logs — pipeline logging."""

    async def test_logs_returns_list(self, client: AsyncClient):
        resp = await client.get("/admin/logs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


@pytest.mark.asyncio
class TestRoleRestrictions:
    """Admin endpoints should require internal_admin role."""

    async def test_client_user_cannot_list_urls(self, client_user: AsyncClient):
        resp = await client_user.get("/admin/urls")
        assert resp.status_code == 403

    async def test_client_user_cannot_create_url(self, client_user: AsyncClient):
        resp = await client_user.post("/admin/urls", json={
            "name": "Sneaky URL",
            "url": "https://evil.com",
        })
        assert resp.status_code == 403

    async def test_client_user_cannot_access_diagnostics(self, client_user: AsyncClient):
        resp = await client_user.get("/admin/diagnostics")
        assert resp.status_code == 403

    async def test_client_user_cannot_access_logs(self, client_user: AsyncClient):
        resp = await client_user.get("/admin/logs")
        assert resp.status_code == 403

"""Tests for the dashboard API — aggregation metrics."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestDashboard:
    """GET /dashboard — aggregated compliance metrics."""

    async def test_dashboard_returns_stats(self, client: AsyncClient, seed_regulation, seed_gaps):
        resp = await client.get("/dashboard")
        assert resp.status_code == 200
        data = resp.json()

        # Should contain top-level stat sections
        assert "regulations" in data
        assert "gaps" in data

    async def test_dashboard_empty_db(self, client: AsyncClient):
        """Dashboard should return zero counts with empty DB, not error."""
        resp = await client.get("/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["regulations"]["total"] == 0
        assert data["gaps"]["total"] == 0

    async def test_dashboard_regulation_counts(self, client: AsyncClient, seed_regulation):
        resp = await client.get("/dashboard")
        data = resp.json()
        assert data["regulations"]["total"] >= 1

    async def test_dashboard_gap_counts(self, client: AsyncClient, seed_gaps):
        resp = await client.get("/dashboard")
        data = resp.json()
        assert data["gaps"]["total"] == 4
        assert data["gaps"]["by_severity"]["critical"] == 1

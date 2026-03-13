"""Tests for the gaps API — list, filter, severity summary, pagination, get-by-id."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestListGaps:
    """GET /gaps — list with filtering and pagination."""

    async def test_list_returns_seeded_gaps(self, client: AsyncClient, seed_gaps):
        resp = await client.get("/gaps")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert len(data["items"]) == 4

    async def test_pagination_fields(self, client: AsyncClient, seed_gaps):
        resp = await client.get("/gaps", params={"page": 1, "page_size": 2})
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total"] == 4
        assert data["total_pages"] == 2
        assert len(data["items"]) == 2

    async def test_filter_by_severity(self, client: AsyncClient, seed_gaps):
        resp = await client.get("/gaps", params={"severity": "critical"})
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["severity"] == "critical"

    async def test_filter_by_invalid_severity_returns_400(self, client: AsyncClient):
        resp = await client.get("/gaps", params={"severity": "ultra_critical"})
        assert resp.status_code == 400

    async def test_filter_by_status(self, client: AsyncClient, seed_gaps):
        resp = await client.get("/gaps", params={"status": "resolved"})
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "resolved"

    async def test_filter_by_open_status(self, client: AsyncClient, seed_gaps):
        """'open' should include both identified and in_progress."""
        resp = await client.get("/gaps", params={"status": "open"})
        data = resp.json()
        assert data["total"] == 3  # critical(identified) + high(in_progress) + medium(identified)
        for item in data["items"]:
            assert item["status"] in ("identified", "in_progress")

    async def test_filter_by_regulation_id(self, client: AsyncClient, seed_gaps, seed_regulation):
        resp = await client.get("/gaps", params={"regulation_id": str(seed_regulation.id)})
        data = resp.json()
        assert data["total"] == 4

    async def test_filter_by_affected_layer(self, client: AsyncClient, seed_gaps):
        resp = await client.get("/gaps", params={"affected_layer": "backend"})
        data = resp.json()
        # Gaps 0 and 2 are backend
        assert data["total"] == 2

    async def test_empty_database_returns_empty(self, client: AsyncClient):
        resp = await client.get("/gaps")
        data = resp.json()
        assert data["total"] == 0


@pytest.mark.asyncio
class TestSeveritySummary:
    """The severity_summary in list_gaps should count the TOTAL dataset, not just the current page."""

    async def test_severity_summary_counts_total(self, client: AsyncClient, seed_gaps):
        """Even with page_size=2, severity_summary should reflect all 4 gaps."""
        resp = await client.get("/gaps", params={"page_size": 2})
        data = resp.json()
        summary = data["severity_summary"]
        assert summary["critical"] == 1
        assert summary["high"] == 1
        assert summary["medium"] == 1
        assert summary["low"] == 1


@pytest.mark.asyncio
class TestGapsSummaryEndpoint:
    """GET /gaps/summary — aggregate counts."""

    async def test_summary_returns_counts(self, client: AsyncClient, seed_gaps):
        resp = await client.get("/gaps/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert data["critical"] == 1
        assert data["high"] == 1
        assert data["medium"] == 1
        assert data["low"] == 1


@pytest.mark.asyncio
class TestGetGap:
    """GET /gaps/{id} — get by ID."""

    async def test_get_by_id(self, client: AsyncClient, seed_gaps):
        gap = seed_gaps[0]
        resp = await client.get(f"/gaps/{gap.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(gap.id)
        assert data["severity"] == "critical"

    async def test_get_nonexistent_returns_404(self, client: AsyncClient):
        import uuid
        resp = await client.get(f"/gaps/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_serialization_fields(self, client: AsyncClient, seed_gaps):
        resp = await client.get(f"/gaps/{seed_gaps[0].id}")
        data = resp.json()
        expected_fields = {
            "id", "source_content_id", "regulation_id", "title",
            "description", "severity", "status", "affected_modules",
            "affected_layer", "is_new_requirement", "deadline", "created_at",
        }
        assert expected_fields.issubset(set(data.keys()))

"""Tests for the regulations API — list, filter, search, pagination, get-by-id, gap analysis request."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestListRegulations:
    """GET /regulations — list with filters, search, and pagination."""

    async def test_list_returns_items(self, client: AsyncClient, seed_regulation):
        resp = await client.get("/regulations")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    async def test_list_pagination_fields(self, client: AsyncClient, seed_regulation):
        resp = await client.get("/regulations", params={"page": 1, "page_size": 10})
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert "total_pages" in data

    async def test_filter_by_status(self, client: AsyncClient, seed_regulation):
        resp = await client.get("/regulations", params={"status": "final_rule"})
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["status"] == "final_rule"

    async def test_filter_by_invalid_status_returns_400(self, client: AsyncClient):
        resp = await client.get("/regulations", params={"status": "invalid_status"})
        assert resp.status_code == 400
        assert "Invalid status" in resp.json()["detail"]

    async def test_filter_by_source(self, client: AsyncClient, seed_regulation):
        resp = await client.get("/regulations", params={"source": "ecfr"})
        data = resp.json()
        for item in data["items"]:
            assert item["source"] == "ecfr"

    async def test_filter_by_min_relevance(self, client: AsyncClient, seed_regulation):
        """Seed regulation has relevance_score=0.95, should pass min_relevance=0.9."""
        resp = await client.get("/regulations", params={"min_relevance": 0.9})
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["relevance_score"] >= 0.9

    async def test_search_by_title(self, client: AsyncClient, seed_regulation):
        resp = await client.get("/regulations", params={"search": "PACE"})
        data = resp.json()
        assert data["total"] >= 1

    async def test_search_no_results(self, client: AsyncClient, seed_regulation):
        resp = await client.get("/regulations", params={"search": "xyznonexistent"})
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_empty_database_returns_empty(self, client: AsyncClient):
        resp = await client.get("/regulations")
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_serialization_fields(self, client: AsyncClient, seed_regulation):
        resp = await client.get("/regulations")
        item = resp.json()["items"][0]
        expected_fields = {
            "id", "source", "title", "summary", "relevance_score",
            "status", "effective_date", "source_url", "document_type",
            "agencies", "affected_areas", "cfr_references", "gap_count",
            "gap_analysis_requested", "ingested_at", "program_area",
            "comment_deadline", "published_date",
        }
        assert expected_fields.issubset(set(item.keys()))


@pytest.mark.asyncio
class TestGetRegulation:
    """GET /regulations/{id} — get by ID."""

    async def test_get_by_id(self, client: AsyncClient, seed_regulation):
        resp = await client.get(f"/regulations/{seed_regulation.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(seed_regulation.id)
        assert data["title"] == seed_regulation.title
        # Detailed fields
        assert "raw_content" in data
        assert "ai_analysis" in data
        assert "key_requirements" in data

    async def test_get_nonexistent_returns_404(self, client: AsyncClient):
        import uuid
        resp = await client.get(f"/regulations/{uuid.uuid4()}")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestRequestGapAnalysis:
    """POST /regulations/{id}/request-gap-analysis — toggle gap analysis flag."""

    async def test_toggle_gap_analysis(self, client: AsyncClient, seed_regulation):
        # Initially False
        assert seed_regulation.gap_analysis_requested is False

        resp = await client.post(f"/regulations/{seed_regulation.id}/request-gap-analysis")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gap_analysis_requested"] is True
        assert "requested" in data["message"]

    async def test_toggle_nonexistent_returns_404(self, client: AsyncClient):
        import uuid
        resp = await client.post(f"/regulations/{uuid.uuid4()}/request-gap-analysis")
        assert resp.status_code == 404

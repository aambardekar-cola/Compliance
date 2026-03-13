"""Tests for the Reports API (executive reports)."""
import uuid

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


class TestListReports:
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/reports")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["page"] == 1

    async def test_list_with_data(self, client: AsyncClient, seed_exec_report):
        resp = await client.get("/reports")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 1
        item = body["items"][0]
        assert "week_start" in item
        assert "week_end" in item
        assert item["metrics"]["new_regulations"] == 5

    async def test_pagination(self, client: AsyncClient, seed_exec_report):
        resp = await client.get("/reports?page=1&page_size=1")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

        resp2 = await client.get("/reports?page=2&page_size=1")
        assert resp2.status_code == 200
        assert len(resp2.json()["items"]) == 0


class TestGetReport:
    async def test_get_by_id(self, client: AsyncClient, seed_exec_report):
        resp = await client.get(f"/reports/{seed_exec_report.id}")
        assert resp.status_code == 200
        body = resp.json()
        # Detailed view includes summary_html, risks, highlights
        assert "summary_html" in body
        assert "risks" in body
        assert len(body["highlights"]) == 2

    async def test_get_nonexistent_returns_404(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        resp = await client.get(f"/reports/{fake_id}")
        assert resp.status_code == 404

    async def test_serialization_fields(self, client: AsyncClient, seed_exec_report):
        resp = await client.get(f"/reports/{seed_exec_report.id}")
        body = resp.json()
        expected_keys = {"id", "week_start", "week_end", "metrics", "sent_at", "created_at",
                         "summary_html", "summary_plain", "risks", "highlights", "sent_to"}
        assert expected_keys == set(body.keys())


class TestReportsRoleRestrictions:
    async def test_client_user_cannot_list_reports(self, client_user: AsyncClient):
        resp = await client_user.get("/reports")
        assert resp.status_code == 403

    async def test_client_user_cannot_get_report(self, client_user: AsyncClient):
        fake_id = uuid.uuid4()
        resp = await client_user.get(f"/reports/{fake_id}")
        assert resp.status_code == 403

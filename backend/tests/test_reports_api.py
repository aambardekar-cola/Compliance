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
        assert body["total"] == 0

    async def test_list_with_data(self, client: AsyncClient, seed_exec_report):
        resp = await client.get("/reports")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 1
        assert body["total"] == 1
        item = body["items"][0]
        assert "week_start" in item
        assert "week_end" in item
        assert item["metrics"]["new_regulations"] == 5
        # List view now includes risks + highlights
        assert "risks" in item
        assert "highlights" in item

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


class TestLatestReport:
    async def test_latest_empty(self, client: AsyncClient):
        resp = await client.get("/reports/latest")
        assert resp.status_code == 200
        assert resp.json()["report"] is None

    async def test_latest_with_data(self, client: AsyncClient, seed_exec_report):
        resp = await client.get("/reports/latest")
        assert resp.status_code == 200
        body = resp.json()
        assert body["report"] is not None
        assert body["report"]["id"] == str(seed_exec_report.id)
        assert "summary_html" in body["report"]


class TestComplianceScores:
    async def test_scores_empty(self, client: AsyncClient):
        resp = await client.get("/reports/scores")
        assert resp.status_code == 200
        body = resp.json()
        assert body["overall_score"] == 100.0
        assert body["module_scores"] == {}

    async def test_scores_with_gaps(self, client: AsyncClient, seed_gaps_for_scoring):
        resp = await client.get("/reports/scores")
        assert resp.status_code == 200
        body = resp.json()
        assert "Pharmacy" in body["module_scores"]
        assert body["module_scores"]["Pharmacy"] == pytest.approx(66.7, abs=0.1)
        assert body["overall_score"] == pytest.approx(66.7, abs=0.1)


class TestAdminReportEndpoints:
    async def test_generate_report_admin_only(self, client_user: AsyncClient):
        resp = await client_user.post("/admin/reports/generate")
        assert resp.status_code == 403

    async def test_send_report_not_found(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        resp = await client.post(f"/admin/reports/{fake_id}/send")
        assert resp.status_code == 404

    async def test_send_report_no_recipients(self, client: AsyncClient, seed_exec_report):
        resp = await client.post(f"/admin/reports/{seed_exec_report.id}/send")
        assert resp.status_code == 400
        assert "recipients" in resp.json()["detail"].lower()


class TestReportsRoleRestrictions:
    async def test_client_user_cannot_list_reports(self, client_user: AsyncClient):
        resp = await client_user.get("/reports")
        assert resp.status_code == 403

    async def test_client_user_cannot_get_report(self, client_user: AsyncClient):
        fake_id = uuid.uuid4()
        resp = await client_user.get(f"/reports/{fake_id}")
        assert resp.status_code == 403

    async def test_client_user_cannot_get_latest(self, client_user: AsyncClient):
        resp = await client_user.get("/reports/latest")
        assert resp.status_code == 403

    async def test_client_user_cannot_get_scores(self, client_user: AsyncClient):
        resp = await client_user.get("/reports/scores")
        assert resp.status_code == 403


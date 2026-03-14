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
        from unittest.mock import patch
        with patch("shared.statsig_client.get_config", return_value=""):
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


class TestReportTrends:
    async def test_trends_empty(self, client: AsyncClient):
        resp = await client.get("/reports/trends")
        assert resp.status_code == 200
        body = resp.json()
        assert body["labels"] == []
        assert body["overall_score"] == []
        assert body["gaps_identified"] == []
        assert body["gaps_resolved"] == []
        assert body["module_scores"] == {}

    async def test_trends_with_data(
        self, client: AsyncClient, seed_exec_reports_for_trends,
    ):
        resp = await client.get("/reports/trends")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["labels"]) == 3
        assert len(body["overall_score"]) == 3
        # Scores are ascending: 70, 80, 90
        assert body["overall_score"] == [70, 80, 90]
        assert "Pharmacy" in body["module_scores"]
        assert "IDT" in body["module_scores"]
        assert len(body["module_scores"]["Pharmacy"]) == 3

    async def test_trends_custom_weeks(
        self, client: AsyncClient, seed_exec_reports_for_trends,
    ):
        resp = await client.get("/reports/trends?weeks=1")
        assert resp.status_code == 200
        body = resp.json()
        # Only the most recent report within last 1 week
        assert len(body["labels"]) <= 1

    async def test_trends_client_forbidden(self, client_user: AsyncClient):
        resp = await client_user.get("/reports/trends")
        assert resp.status_code == 403


class TestReportRecipients:
    async def test_get_recipients_empty(self, client: AsyncClient):
        from unittest.mock import patch
        with patch("shared.statsig_client.get_config", return_value=""):
            resp = await client.get("/admin/reports/recipients")
        assert resp.status_code == 200
        assert resp.json()["emails"] == []

    async def test_get_recipients_from_db(
        self, client: AsyncClient, seed_system_config_recipients,
    ):
        resp = await client.get("/admin/reports/recipients")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body["emails"]) == {"admin@test.com", "ceo@test.com"}

    async def test_update_recipients(self, client: AsyncClient):
        # PUT new recipients
        resp = await client.put(
            "/admin/reports/recipients",
            json={"emails": ["a@test.com", "b@test.com"]},
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

        # GET should reflect the updated list
        resp2 = await client.get("/admin/reports/recipients")
        assert set(resp2.json()["emails"]) == {"a@test.com", "b@test.com"}

    async def test_update_recipients_overwrite(self, client: AsyncClient):
        # First set
        await client.put(
            "/admin/reports/recipients",
            json={"emails": ["first@test.com"]},
        )
        # Overwrite
        resp = await client.put(
            "/admin/reports/recipients",
            json={"emails": ["second@test.com"]},
        )
        assert resp.status_code == 200
        resp2 = await client.get("/admin/reports/recipients")
        assert resp2.json()["emails"] == ["second@test.com"]

    async def test_update_invalid_email(self, client: AsyncClient):
        resp = await client.put(
            "/admin/reports/recipients",
            json={"emails": ["not-an-email"]},
        )
        assert resp.status_code == 422

    async def test_recipients_admin_only(self, client_user: AsyncClient):
        resp = await client_user.get("/admin/reports/recipients")
        assert resp.status_code == 403
        resp2 = await client_user.put(
            "/admin/reports/recipients",
            json={"emails": ["x@test.com"]},
        )
        assert resp2.status_code == 403


class TestCustomDateRangeGeneration:
    async def test_generate_with_date_range_validation(self, client: AsyncClient):
        """POST with invalid dates returns 400."""
        resp = await client.post(
            "/admin/reports/generate",
            json={"week_start": "not-a-date", "week_end": "2026-01-14"},
        )
        assert resp.status_code == 400

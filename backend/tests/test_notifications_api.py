"""Tests for the Notifications and Pipeline Runs API."""
import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from shared.models import PipelineRun, PipelineRunType, PipelineRunStatus


pytestmark = pytest.mark.asyncio

# NOTE: notifications.router is mounted at /admin prefix in main.py


# ---------- Notifications ----------

class TestListNotifications:
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/admin/notifications")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["unread_count"] == 0

    async def test_list_with_data(self, client: AsyncClient, seed_notification):
        resp = await client.get("/admin/notifications")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["unread_count"] == 1
        assert body["items"][0]["title"] == "Analysis Complete"

    async def test_unread_filter(self, client: AsyncClient, seed_notification, db_session):
        # Mark the notification as read
        seed_notification.is_read = True
        await db_session.commit()
        resp = await client.get("/admin/notifications?unread_only=true")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_pagination(self, client: AsyncClient, seed_notification):
        resp = await client.get("/admin/notifications?page=1&page_size=1")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1


class TestUnreadCount:
    async def test_unread_count_zero(self, client: AsyncClient):
        resp = await client.get("/admin/notifications/unread-count")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0

    async def test_unread_count_with_data(self, client: AsyncClient, seed_notification):
        resp = await client.get("/admin/notifications/unread-count")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 1


class TestMarkRead:
    async def test_mark_single_read(self, client: AsyncClient, seed_notification):
        resp = await client.post(f"/admin/notifications/{seed_notification.id}/read")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        # Verify unread count dropped
        check = await client.get("/admin/notifications/unread-count")
        assert check.json()["unread_count"] == 0

    async def test_mark_nonexistent_returns_404(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        resp = await client.post(f"/admin/notifications/{fake_id}/read")
        assert resp.status_code == 404

    async def test_mark_all_read(self, client: AsyncClient, seed_notification):
        resp = await client.post("/admin/notifications/read-all")
        assert resp.status_code == 200
        check = await client.get("/admin/notifications/unread-count")
        assert check.json()["unread_count"] == 0


# ---------- Pipeline Runs ----------

class TestListPipelineRuns:
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/admin/pipeline-runs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_list_with_data(self, client: AsyncClient, seed_pipeline_run):
        resp = await client.get("/admin/pipeline-runs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["run_type"] == "analysis"
        assert body["items"][0]["status"] == "completed"

    async def test_filter_by_type(self, client: AsyncClient, seed_pipeline_run):
        resp = await client.get("/admin/pipeline-runs?run_type=analysis")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp2 = await client.get("/admin/pipeline-runs?run_type=scraper")
        assert resp2.status_code == 200
        assert resp2.json()["total"] == 0

    async def test_filter_by_status(self, client: AsyncClient, seed_pipeline_run):
        resp = await client.get("/admin/pipeline-runs?run_status=completed")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp2 = await client.get("/admin/pipeline-runs?run_status=failed")
        assert resp2.status_code == 200
        assert resp2.json()["total"] == 0


class TestGetPipelineRun:
    async def test_get_by_id(self, client: AsyncClient, seed_pipeline_run):
        resp = await client.get(f"/admin/pipeline-runs/{seed_pipeline_run.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["regulations_added"] == 5
        assert body["gaps_added"] == 3

    async def test_get_nonexistent_returns_404(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        resp = await client.get(f"/admin/pipeline-runs/{fake_id}")
        assert resp.status_code == 404


class TestCleanupStaleRuns:
    async def test_cleanup_no_stale(self, client: AsyncClient, seed_pipeline_run):
        resp = await client.post("/admin/pipeline-runs/cleanup-stale?max_age_minutes=10")
        assert resp.status_code == 200
        assert resp.json()["cleaned"] == 0

    async def test_cleanup_stale_run(self, client: AsyncClient, db_session):
        # Create a stale "started" run from 30 minutes ago
        stale = PipelineRun(
            id=uuid.uuid4(),
            run_type=PipelineRunType.SCRAPER,
            status=PipelineRunStatus.STARTED,
            started_at=datetime.utcnow() - timedelta(minutes=30),
        )
        db_session.add(stale)
        await db_session.commit()

        resp = await client.post("/admin/pipeline-runs/cleanup-stale?max_age_minutes=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cleaned"] == 1
        assert str(stale.id) in body["run_ids"]


# ---------- Role Restrictions ----------

class TestNotificationRoleRestrictions:
    async def test_client_user_cannot_list_notifications(self, client_user: AsyncClient):
        resp = await client_user.get("/admin/notifications")
        assert resp.status_code == 403

    async def test_client_user_cannot_get_unread_count(self, client_user: AsyncClient):
        resp = await client_user.get("/admin/notifications/unread-count")
        assert resp.status_code == 403

    async def test_client_user_cannot_list_pipeline_runs(self, client_user: AsyncClient):
        resp = await client_user.get("/admin/pipeline-runs")
        assert resp.status_code == 403

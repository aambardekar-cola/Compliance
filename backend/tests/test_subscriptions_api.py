"""Tests for the Subscriptions API."""
import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


class TestListSubscriptions:
    async def test_list_returns_default_features(self, client: AsyncClient):
        """Internal users with no tenant get default (inactive) subscriptions."""
        resp = await client.get("/subscriptions")
        assert resp.status_code == 200
        body = resp.json()
        subs = body["subscriptions"]
        assert len(subs) == 5  # 5 AVAILABLE_FEATURES
        assert all(not s["is_active"] for s in subs)
        features = {s["feature"] for s in subs}
        assert "new_regulations" in features
        assert "gap_alerts" in features

    async def test_list_with_tenant(self, client_user: AsyncClient, seed_tenant):
        """Client user with matching tenant gets subscriptions."""
        resp = await client_user.get("/subscriptions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["subscriptions"]) == 5


class TestUpdateSubscription:
    async def test_invalid_feature_returns_400(self, client: AsyncClient):
        resp = await client.put(
            "/subscriptions/nonexistent_feature",
            json={"is_active": True},
        )
        assert resp.status_code == 400

    async def test_client_user_cannot_update(self, client_user: AsyncClient):
        """Client users (non-admin) get 403 on subscription updates."""
        resp = await client_user.put(
            "/subscriptions/gap_alerts",
            json={"is_active": True},
        )
        assert resp.status_code == 403

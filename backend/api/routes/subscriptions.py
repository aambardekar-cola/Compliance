"""Subscriptions API routes — manage client notification preferences."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session_dependency
from shared.models import Subscription, Tenant
from api.middleware.auth import get_current_user

router = APIRouter()

AVAILABLE_FEATURES = [
    "new_regulations",
    "gap_alerts",
    "deadline_reminders",
    "compliance_updates",
    "resolution_notices",
]


class UpdateSubscriptionRequest(BaseModel):
    """Request body for updating a subscription."""
    is_active: bool
    notification_email: Optional[str] = None


@router.get("/subscriptions")
async def list_subscriptions(
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """List notification subscriptions for the current tenant."""
    user = get_current_user(request)

    if not user.tenant_id and not user.is_internal:
        raise HTTPException(400, "No tenant associated with user")

    # Get tenant DB ID from Descope tenant ID
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.descope_tenant_id == user.tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()

    if not tenant:
        # Return default subscriptions if tenant not yet provisioned
        return {
            "subscriptions": [
                {"feature": f, "is_active": False, "notification_email": None}
                for f in AVAILABLE_FEATURES
            ]
        }

    result = await db.execute(
        select(Subscription).where(Subscription.tenant_id == tenant.id)
    )
    subs = {s.feature: s for s in result.scalars().all()}

    return {
        "subscriptions": [
            {
                "feature": f,
                "is_active": subs[f].is_active if f in subs else False,
                "notification_email": subs[f].notification_email if f in subs else None,
            }
            for f in AVAILABLE_FEATURES
        ]
    }


@router.put("/subscriptions/{feature}")
async def update_subscription(
    feature: str,
    body: UpdateSubscriptionRequest,
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """Update a notification subscription for the current tenant."""
    user = get_current_user(request)

    if feature not in AVAILABLE_FEATURES:
        raise HTTPException(400, f"Invalid feature: {feature}")

    if not user.is_admin:
        raise HTTPException(403, "Only admins can manage subscriptions")

    # Get or create tenant
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.descope_tenant_id == user.tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()

    if not tenant:
        tenant = Tenant(
            name=user.tenant_name or "Unknown",
            descope_tenant_id=user.tenant_id,
        )
        db.add(tenant)
        await db.flush()

    # Get or create subscription
    sub_result = await db.execute(
        select(Subscription).where(
            Subscription.tenant_id == tenant.id,
            Subscription.feature == feature,
        )
    )
    sub = sub_result.scalar_one_or_none()

    if sub:
        sub.is_active = body.is_active
        sub.notification_email = body.notification_email
    else:
        sub = Subscription(
            tenant_id=tenant.id,
            feature=feature,
            is_active=body.is_active,
            notification_email=body.notification_email,
        )
        db.add(sub)

    await db.commit()

    return {
        "feature": feature,
        "is_active": body.is_active,
        "notification_email": body.notification_email,
        "message": "Subscription updated",
    }

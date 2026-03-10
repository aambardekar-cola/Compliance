"""Admin notification and pipeline run endpoints."""
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session_dependency
from shared.models import (
    AdminNotification, PipelineRun,
    NotificationType, PipelineRunType, PipelineRunStatus,
)
from api.middleware.auth import require_role

router = APIRouter()


# ---- Schemas ----

class NotificationOut(BaseModel):
    id: UUID
    pipeline_run_id: Optional[UUID] = None
    notification_type: str
    title: str
    message: str
    is_read: bool
    metadata_json: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListOut(BaseModel):
    items: List[NotificationOut]
    total: int
    unread_count: int


class PipelineRunOut(BaseModel):
    id: UUID
    run_type: str
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    urls_scraped: int = 0
    chunks_processed: int = 0
    regulations_added: int = 0
    gaps_added: int = 0
    errors_count: int = 0
    error_message: Optional[str] = None
    details: Optional[dict] = None

    class Config:
        from_attributes = True


class PipelineRunListOut(BaseModel):
    items: List[PipelineRunOut]
    total: int


class UnreadCountOut(BaseModel):
    unread_count: int


# ---- Notification Endpoints ----

@router.get("/notifications", response_model=NotificationListOut)
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    session: AsyncSession = Depends(get_session_dependency),
    _user=Depends(require_role("internal_admin")),
):
    """List admin notifications, newest first."""
    query = select(AdminNotification).order_by(desc(AdminNotification.created_at))
    count_query = select(func.count()).select_from(AdminNotification)

    if unread_only:
        query = query.where(AdminNotification.is_read == False)  # noqa: E712
        count_query = count_query.where(AdminNotification.is_read == False)  # noqa: E712

    total = (await session.execute(count_query)).scalar() or 0

    # Unread count always
    unread_count = (await session.execute(
        select(func.count()).select_from(AdminNotification).where(
            AdminNotification.is_read == False  # noqa: E712
        )
    )).scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await session.execute(query)
    notifications = result.scalars().all()

    return NotificationListOut(
        items=[NotificationOut.model_validate(n) for n in notifications],
        total=total,
        unread_count=unread_count,
    )


@router.get("/notifications/unread-count", response_model=UnreadCountOut)
async def get_unread_count(
    session: AsyncSession = Depends(get_session_dependency),
    _user=Depends(require_role("internal_admin")),
):
    """Get the count of unread notifications (for the bell badge)."""
    count = (await session.execute(
        select(func.count()).select_from(AdminNotification).where(
            AdminNotification.is_read == False  # noqa: E712
        )
    )).scalar() or 0
    return UnreadCountOut(unread_count=count)


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    session: AsyncSession = Depends(get_session_dependency),
    _user=Depends(require_role("internal_admin")),
):
    """Mark a single notification as read."""
    notification = await session.get(AdminNotification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    await session.commit()
    return {"status": "ok", "id": str(notification_id)}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    session: AsyncSession = Depends(get_session_dependency),
    _user=Depends(require_role("internal_admin")),
):
    """Mark all notifications as read."""
    await session.execute(
        update(AdminNotification).where(
            AdminNotification.is_read == False  # noqa: E712
        ).values(is_read=True)
    )
    await session.commit()
    return {"status": "ok", "message": "All notifications marked as read"}


# ---- Pipeline Run Endpoints ----

@router.get("/pipeline-runs", response_model=PipelineRunListOut)
async def list_pipeline_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    run_type: Optional[str] = Query(None),
    run_status: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session_dependency),
    _user=Depends(require_role("internal_admin")),
):
    """List pipeline runs, newest first."""
    query = select(PipelineRun).order_by(desc(PipelineRun.started_at))
    count_query = select(func.count()).select_from(PipelineRun)

    if run_type:
        query = query.where(PipelineRun.run_type == run_type)
        count_query = count_query.where(PipelineRun.run_type == run_type)
    if run_status:
        query = query.where(PipelineRun.status == run_status)
        count_query = count_query.where(PipelineRun.status == run_status)

    total = (await session.execute(count_query)).scalar() or 0
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await session.execute(query)
    runs = result.scalars().all()

    return PipelineRunListOut(
        items=[PipelineRunOut.model_validate(r) for r in runs],
        total=total,
    )


@router.get("/pipeline-runs/{run_id}", response_model=PipelineRunOut)
async def get_pipeline_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_session_dependency),
    _user=Depends(require_role("internal_admin")),
):
    """Get details of a single pipeline run."""
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return PipelineRunOut.model_validate(run)

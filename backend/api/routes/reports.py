"""Reports API routes — executive summary reports."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session_dependency
from shared.models import ExecReport
from api.middleware.auth import get_current_user

router = APIRouter()


@router.get("/reports")
async def list_reports(
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    """List executive summary reports."""
    user = get_current_user(request)

    if not user.is_internal:
        raise HTTPException(403, "Executive reports are internal only")

    query = (
        select(ExecReport)
        .order_by(desc(ExecReport.week_start))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    reports = result.scalars().all()

    return {
        "items": [_serialize_report(r) for r in reports],
        "page": page,
        "page_size": page_size,
    }


@router.get("/reports/{report_id}")
async def get_report(
    report_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """Get a specific executive report."""
    user = get_current_user(request)

    if not user.is_internal:
        raise HTTPException(403, "Executive reports are internal only")

    result = await db.execute(
        select(ExecReport).where(ExecReport.id == report_id)
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(404, "Report not found")

    return _serialize_report(report, detailed=True)


def _serialize_report(report: ExecReport, detailed: bool = False) -> dict:
    """Serialize an ExecReport model to API response."""
    data = {
        "id": str(report.id),
        "week_start": report.week_start.isoformat(),
        "week_end": report.week_end.isoformat(),
        "metrics": report.metrics or {},
        "sent_at": report.sent_at.isoformat() if report.sent_at else None,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }

    if detailed:
        data.update({
            "summary_html": report.summary_html,
            "summary_plain": report.summary_plain,
            "risks": report.risks or [],
            "highlights": report.highlights or [],
            "sent_to": report.sent_to or [],
        })

    return data

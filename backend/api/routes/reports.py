"""Reports API routes — executive summary reports and compliance scoring."""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session_dependency
from shared.models import ExecReport
from shared import statsig_client
from api.middleware.auth import get_current_user
from reporting.scoring import compute_module_scores, compute_overall_score

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

    # Total count
    count_result = await db.execute(
        select(func.count()).select_from(ExecReport)
    )
    total = count_result.scalar() or 0

    # Paginated items
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
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/reports/latest")
async def get_latest_report(
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """Get the most recent executive report."""
    user = get_current_user(request)

    if not user.is_internal:
        raise HTTPException(403, "Executive reports are internal only")

    result = await db.execute(
        select(ExecReport).order_by(desc(ExecReport.week_start)).limit(1)
    )
    report = result.scalar_one_or_none()

    if not report:
        return {"report": None}

    return {"report": _serialize_report(report, detailed=True)}


@router.get("/reports/scores")
async def get_compliance_scores(
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """Get live per-module compliance scores."""
    user = get_current_user(request)

    if not user.is_internal:
        raise HTTPException(403, "Compliance scores are internal only")

    module_scores = await compute_module_scores(db)
    overall_score = await compute_overall_score(db)

    return {
        "overall_score": overall_score,
        "module_scores": module_scores,
    }


@router.get("/reports/trends")
async def get_report_trends(
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
    weeks: int = Query(None, ge=1, le=52),
):
    """Get historical compliance trends from past reports.

    Returns time-series data for charting: scores, gaps identified/resolved.
    """
    user = get_current_user(request)

    if not user.is_internal:
        raise HTTPException(403, "Compliance trends are internal only")

    if weeks is None:
        weeks = statsig_client.get_config("reporting", "trend_weeks", 12)

    cutoff = datetime.utcnow() - timedelta(weeks=weeks)

    result = await db.execute(
        select(ExecReport)
        .where(ExecReport.week_start >= cutoff.date())
        .order_by(ExecReport.week_start)
    )
    reports = result.scalars().all()

    labels = []
    overall_scores = []
    gaps_identified = []
    gaps_resolved = []
    module_scores_series: dict = {}

    for r in reports:
        labels.append(r.week_start.isoformat())
        metrics = r.metrics or {}
        overall_scores.append(metrics.get("compliance_score", 0))
        gaps_identified.append(metrics.get("gaps_identified", 0))
        gaps_resolved.append(metrics.get("gaps_resolved", 0))

        # Per-module scores from the metrics snapshot
        for mod, score in metrics.get("module_scores", {}).items():
            if mod not in module_scores_series:
                module_scores_series[mod] = []
            module_scores_series[mod].append(score)

    return {
        "labels": labels,
        "overall_score": overall_scores,
        "module_scores": module_scores_series,
        "gaps_identified": gaps_identified,
        "gaps_resolved": gaps_resolved,
        "weeks": weeks,
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
        "risks": report.risks or [],
        "highlights": report.highlights or [],
        "sent_at": report.sent_at.isoformat() if report.sent_at else None,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }

    if detailed:
        data.update({
            "summary_html": report.summary_html,
            "summary_plain": report.summary_plain,
            "sent_to": report.sent_to or [],
        })

    return data


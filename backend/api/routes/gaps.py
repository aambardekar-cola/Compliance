"""Gap Analysis API routes — view compliance gaps and effort estimates."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session_dependency
from shared.models import GapAnalysis, GapSeverity, GapStatus

router = APIRouter()

@router.get("/gaps")
async def list_gaps(
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
    regulation_id: Optional[UUID] = Query(None, description="Filter by regulation"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    status: Optional[str] = Query(None, description="Filter by status"),
    team: Optional[str] = Query(None, description="Filter by assigned team"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List compliance gaps with filtering and pagination."""
    query = select(GapAnalysis)

    if regulation_id:
        query = query.where(GapAnalysis.regulation_id == regulation_id)

    if severity:
        try:
            query = query.where(GapAnalysis.severity == GapSeverity(severity))
        except ValueError:
            raise HTTPException(400, f"Invalid severity: {severity}")

    if status:
        try:
            query = query.where(GapAnalysis.status == GapStatus(status))
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")

    if team:
        query = query.where(GapAnalysis.assigned_team == team)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # Apply pagination
    query = (
        query
        .order_by(
            desc(GapAnalysis.severity == GapSeverity.CRITICAL),
            desc(GapAnalysis.severity == GapSeverity.HIGH),
            desc(GapAnalysis.created_at),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    gaps = result.scalars().all()

    return {
        "items": [_serialize_gap(g) for g in gaps],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/gaps/summary")
async def get_gaps_summary(
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """Get gap analysis summary by team and severity."""
    query = select(
        GapAnalysis.assigned_team,
        GapAnalysis.severity,
        func.count(GapAnalysis.id).label("count"),
        func.sum(GapAnalysis.effort_hours).label("total_hours"),
    ).group_by(GapAnalysis.assigned_team, GapAnalysis.severity)

    result = await db.execute(query)
    rows = result.all()

    summary = {}
    for row in rows:
        team = row.assigned_team or "unassigned"
        if team not in summary:
            summary[team] = {"total_gaps": 0, "total_hours": 0, "by_severity": {}}
        summary[team]["total_gaps"] += row.count
        summary[team]["total_hours"] += row.total_hours or 0
        summary[team]["by_severity"][row.severity.value] = row.count

    return {"teams": summary}


@router.get("/gaps/{gap_id}")
async def get_gap(
    gap_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """Get detailed gap analysis information."""
    result = await db.execute(
        select(GapAnalysis).where(GapAnalysis.id == gap_id)
    )
    gap = result.scalar_one_or_none()

    if not gap:
        raise HTTPException(404, "Gap not found")

    return _serialize_gap(gap, detailed=True)


def _serialize_gap(gap: GapAnalysis, detailed: bool = False) -> dict:
    """Serialize a GapAnalysis model to API response."""
    data = {
        "id": str(gap.id),
        "regulation_id": str(gap.regulation_id),
        "title": gap.title,
        "description": gap.description,
        "severity": gap.severity.value if gap.severity else None,
        "status": gap.status.value if gap.status else None,
        "assigned_team": gap.assigned_team,
        "effort_hours": gap.effort_hours,
        "effort_story_points": gap.effort_story_points,
        "jira_epic_key": gap.jira_epic_key,
        "jira_epic_url": gap.jira_epic_url,
        "created_at": gap.created_at.isoformat() if gap.created_at else None,
    }

    if detailed:
        data.update({
            "affected_code": gap.affected_code or [],
            "affected_components": gap.affected_components or [],
        })

    return data

"""Gap Analysis API routes — view compliance gaps extracted by the AI Engine."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from shared.db import get_session_dependency
from shared.models import ComplianceGap, GapSeverity, GapStatus, AffectedLayer

router = APIRouter()

@router.get("/gaps")
async def list_gaps(
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    status: Optional[str] = Query(None, description="Filter by status"),
    module: Optional[str] = Query(None, description="Filter by affected PCO module"),
    regulation_id: Optional[str] = Query(None, description="Filter by parent regulation"),
    affected_layer: Optional[str] = Query(None, description="Filter by affected layer (frontend/backend/both)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List compliance gaps with filtering and pagination."""
    query = select(ComplianceGap).options(
        joinedload(ComplianceGap.scraped_content),
        joinedload(ComplianceGap.regulation),
    )

    if severity:
        try:
            query = query.where(ComplianceGap.severity == GapSeverity(severity.lower()))
        except ValueError:
            raise HTTPException(400, f"Invalid severity: {severity}")

    if status:
        if status.lower() == 'open':
            query = query.where(ComplianceGap.status.in_([GapStatus.IDENTIFIED, GapStatus.IN_PROGRESS]))
        else:
            try:
                query = query.where(ComplianceGap.status == GapStatus(status.lower()))
            except ValueError:
                raise HTTPException(400, f"Invalid status: {status}")

    # Note: affected_modules is a JSON array.
    
    if regulation_id:
        try:
            query = query.where(ComplianceGap.regulation_id == UUID(regulation_id))
        except ValueError:
            raise HTTPException(400, f"Invalid regulation_id: {regulation_id}")
    
    if affected_layer:
        try:
            query = query.where(ComplianceGap.affected_layer == AffectedLayer(affected_layer.lower()))
        except ValueError:
            raise HTTPException(400, f"Invalid affected_layer: {affected_layer}")
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # Apply pagination and sorting
    query = (
        query
        .order_by(
            desc(ComplianceGap.severity == GapSeverity.CRITICAL.value),
            desc(ComplianceGap.severity == GapSeverity.HIGH.value),
            desc(ComplianceGap.created_at),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    gaps = result.scalars().all()

    # Get total severity summary (across all data, not just current page)
    severity_subquery = (
        select(
            ComplianceGap.severity,
            func.count(ComplianceGap.id).label("count"),
        )
        .select_from(query.subquery())
        .group_by(ComplianceGap.severity)
    )
    severity_result = await db.execute(severity_subquery)
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for row in severity_result.all():
        sev_value = row.severity.value if row.severity else "low"
        if sev_value in severity_counts:
            severity_counts[sev_value] = row.count

    return {
        "items": [_serialize_gap(g) for g in gaps],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "severity_summary": severity_counts,
    }


def _count_severities(gaps) -> dict:
    """Count gaps by severity for inline summary."""
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for g in gaps:
        sev = g.severity.value if g.severity else "low"
        if sev in counts:
            counts[sev] += 1
    return counts


@router.get("/gaps/summary")
async def get_gaps_summary(
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """Get gap analysis summary by severity."""
    # Simplified summary for the dashboard
    query = select(
        ComplianceGap.severity,
        func.count(ComplianceGap.id).label("count"),
    ).group_by(ComplianceGap.severity)

    result = await db.execute(query)
    rows = result.all()

    summary = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "total": 0
    }
    
    for row in rows:
        sev_value = row.severity.value if row.severity else "low"
        summary[sev_value] = row.count
        summary["total"] += row.count

    return summary


@router.get("/gaps/{gap_id}")
async def get_gap(
    gap_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """Get detailed gap analysis information."""
    result = await db.execute(
        select(ComplianceGap).where(ComplianceGap.id == gap_id)
    )
    gap = result.scalar_one_or_none()

    if not gap:
        raise HTTPException(404, "Gap not found")

    return _serialize_gap(gap, detailed=True)


def _serialize_gap(gap: ComplianceGap, detailed: bool = False) -> dict:
    """Serialize a ComplianceGap model to API response."""
    data = {
        "id": str(gap.id),
        "source_content_id": str(gap.scraped_content_id),
        "regulation_id": str(gap.regulation_id) if gap.regulation_id else None,
        "title": gap.title,
        "description": gap.description,
        "severity": gap.severity.value if gap.severity else None,
        "status": gap.status.value if gap.status else None,
        "affected_modules": gap.affected_modules or [],
        "affected_layer": gap.affected_layer.value if gap.affected_layer else "unknown",
        "is_new_requirement": gap.is_new_requirement,
        "deadline": gap.deadline.isoformat() if gap.deadline else None,
        "created_at": gap.created_at.isoformat() if gap.created_at else None,
    }

    # Include parent regulation info if loaded
    if gap.regulation:
        data["regulation"] = {
            "id": str(gap.regulation.id),
            "title": gap.regulation.title,
            "cfr_references": gap.regulation.cfr_references or [],
            "affected_areas": gap.regulation.affected_areas or [],
        }

    return data

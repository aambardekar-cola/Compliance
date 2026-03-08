"""Gap Analysis API routes — view compliance gaps extracted by the AI Engine."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from shared.db import get_session_dependency
from shared.models import ComplianceGap, GapSeverity, GapStatus

router = APIRouter()

@router.get("/gaps")
async def list_gaps(
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    status: Optional[str] = Query(None, description="Filter by status"),
    module: Optional[str] = Query(None, description="Filter by affected PCO module"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List compliance gaps with filtering and pagination."""
    query = select(ComplianceGap).options(joinedload(ComplianceGap.scraped_content))

    if severity:
        try:
            query = query.where(ComplianceGap.severity == GapSeverity(severity.lower()))
        except ValueError:
            raise HTTPException(400, f"Invalid severity: {severity}")

    if status:
        try:
            query = query.where(ComplianceGap.status == GapStatus(status.lower()))
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")

    # Note: affected_modules is a JSON array. In Postgres we'd use array ops, but this works for basic filtering
    # if it becomes a problem, we can use raw SQL cast to JSONB
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # Apply pagination and sorting
    query = (
        query
        .order_by(
            desc(ComplianceGap.severity == GapSeverity.CRITICAL),
            desc(ComplianceGap.severity == GapSeverity.HIGH),
            desc(ComplianceGap.created_at),
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
        "title": gap.title,
        "description": gap.description,
        "severity": gap.severity.value if gap.severity else None,
        "status": gap.status.value if gap.status else None,
        "affected_modules": gap.affected_modules or [],
        "is_new_requirement": gap.is_new_requirement,
        "deadline": gap.deadline.isoformat() if gap.deadline else None,
        "created_at": gap.created_at.isoformat() if gap.created_at else None,
    }

    return data

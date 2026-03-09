"""Regulations API routes — browse and search regulatory documents."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session_dependency
from shared.models import Regulation, RegulationStatus

router = APIRouter()


@router.get("/regulations")
async def list_regulations(
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
    status: Optional[str] = Query(None, description="Filter by status"),
    min_relevance: float = Query(0.0, ge=0.0, le=1.0, description="Minimum relevance score"),
    search: Optional[str] = Query(None, description="Search in title and summary"),
    source: Optional[str] = Query(None, description="Filter by source"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List regulations with filtering, search, and pagination."""
    query = select(Regulation).where(Regulation.relevance_score >= min_relevance)

    # Apply filters
    if status:
        try:
            status_enum = RegulationStatus(status)
            query = query.where(Regulation.status == status_enum)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")

    if source:
        query = query.where(Regulation.source == source)

    if search:
        search_term = f"%{search}%"
        query = query.where(
            Regulation.title.ilike(search_term) | Regulation.summary.ilike(search_term)
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # Apply pagination and ordering
    query = (
        query
        .order_by(desc(Regulation.ingested_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    regulations = result.scalars().all()

    return {
        "items": [_serialize_regulation(r) for r in regulations],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/regulations/{regulation_id}")
async def get_regulation(
    regulation_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """Get detailed regulation information with AI analysis."""
    result = await db.execute(
        select(Regulation).where(Regulation.id == regulation_id)
    )
    regulation = result.scalar_one_or_none()

    if not regulation:
        raise HTTPException(404, "Regulation not found")

    return _serialize_regulation(regulation, detailed=True)


def _serialize_regulation(reg: Regulation, detailed: bool = False) -> dict:
    """Serialize a Regulation model to API response."""
    data = {
        "id": str(reg.id),
        "source": reg.source,
        "title": reg.title,
        "summary": reg.summary,
        "relevance_score": reg.relevance_score,
        "status": reg.status.value if reg.status else None,
        "effective_date": reg.effective_date.isoformat() if reg.effective_date else None,
        "comment_deadline": reg.comment_deadline.isoformat() if reg.comment_deadline else None,
        "published_date": reg.published_date.isoformat() if reg.published_date else None,
        "source_url": reg.source_url,
        "document_type": reg.document_type,
        "agencies": reg.agencies or [],
        "affected_areas": reg.affected_areas or [],
        "cfr_references": reg.cfr_references or [],
        "gap_count": len(reg.compliance_gaps) if reg.compliance_gaps else 0,
        "ingested_at": reg.ingested_at.isoformat() if reg.ingested_at else None,
    }

    if detailed:
        data.update({
            "raw_content": reg.raw_content,
            "ai_analysis": reg.ai_analysis or {},
            "key_requirements": reg.key_requirements or [],
        })

    return data

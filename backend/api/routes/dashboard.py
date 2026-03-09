"""Dashboard API routes — aggregated compliance metrics."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session_dependency
from shared.models import (
    Regulation, ComplianceGap, Communication,
    RegulationStatus, GapSeverity, GapStatus, CommunicationStatus,
)
from api.middleware.auth import get_current_user
from shared.auth import CurrentUser

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """Get aggregated compliance dashboard metrics."""
    user = get_current_user(request)

    # ---- Regulation Stats ----
    reg_query = select(
        func.count(Regulation.id).label("total"),
        func.count(case((Regulation.status == RegulationStatus.PROPOSED, 1))).label("proposed"),
        func.count(case((Regulation.status == RegulationStatus.COMMENT_PERIOD, 1))).label("comment_period"),
        func.count(case((Regulation.status == RegulationStatus.FINAL_RULE, 1))).label("final_rule"),
        func.count(case((Regulation.status == RegulationStatus.EFFECTIVE, 1))).label("effective"),
        func.avg(Regulation.relevance_score).label("avg_relevance"),
    ).where(Regulation.relevance_score >= 0.5)

    reg_result = await db.execute(reg_query)
    reg_stats = reg_result.one()

    # ---- Gap Analysis Stats (from AI extracted ComplianceGap) ----
    gap_query = select(
        func.count(ComplianceGap.id).label("total"),
        func.count(case((ComplianceGap.severity == GapSeverity.CRITICAL, 1))).label("critical"),
        func.count(case((ComplianceGap.severity == GapSeverity.HIGH, 1))).label("high"),
        func.count(case((ComplianceGap.status == GapStatus.IDENTIFIED, 1))).label("open"),
        func.count(case((ComplianceGap.status == GapStatus.RESOLVED, 1))).label("resolved"),
        func.cast(0, func.Integer).label("total_effort_hours"), # ComplianceGap doesn't track effort yet
    )

    gap_result = await db.execute(gap_query)
    gap_stats = gap_result.one()

    # ---- Communication Stats ----
    comm_query = select(
        func.count(Communication.id).label("total"),
        func.count(case((Communication.status == CommunicationStatus.DRAFT, 1))).label("drafts"),
        func.count(case((Communication.status == CommunicationStatus.PENDING_APPROVAL, 1))).label("pending"),
        func.count(case((Communication.status == CommunicationStatus.SENT, 1))).label("sent"),
    )

    # Filter by tenant for client users
    if not user.is_internal and user.tenant_id:
        from shared.models import Tenant
        tenant_result = await db.execute(
            select(Tenant.id).where(Tenant.descope_tenant_id == user.tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        if tenant:
            comm_query = comm_query.where(Communication.tenant_id == tenant)

    comm_result = await db.execute(comm_query)
    comm_stats = comm_result.one()

    # ---- Upcoming Deadlines ----
    today = datetime.utcnow().date()
    upcoming_query = (
        select(Regulation.id, Regulation.title, Regulation.effective_date, Regulation.status)
        .where(
            Regulation.effective_date >= today,
            Regulation.effective_date <= today + timedelta(days=90),
            Regulation.relevance_score >= 0.5,
        )
        .order_by(Regulation.effective_date)
        .limit(10)
    )
    upcoming_result = await db.execute(upcoming_query)
    upcoming_deadlines = [
        {
            "id": str(row.id),
            "title": row.title,
            "effective_date": row.effective_date.isoformat() if row.effective_date else None,
            "status": row.status.value,
        }
        for row in upcoming_result.all()
    ]

    return {
        "regulations": {
            "total": reg_stats.total,
            "proposed": reg_stats.proposed,
            "comment_period": reg_stats.comment_period,
            "final_rule": reg_stats.final_rule,
            "effective": reg_stats.effective,
            "avg_relevance": round(float(reg_stats.avg_relevance or 0), 2),
        },
        "gaps": {
            "total": gap_stats.total,
            "critical": gap_stats.critical,
            "high": gap_stats.high,
            "open": gap_stats.open,
            "resolved": gap_stats.resolved,
            "total_effort_hours": gap_stats.total_effort_hours or 0,
        },
        "communications": {
            "total": comm_stats.total,
            "drafts": comm_stats.drafts,
            "pending_approval": comm_stats.pending,
            "sent": comm_stats.sent,
        },
        "upcoming_deadlines": upcoming_deadlines,
    }

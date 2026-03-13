"""Per-module compliance scoring engine.

Computes a compliance score (0-100) for each PCO module based on the
ratio of resolved/accepted gaps to total gaps.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import (
    ComplianceGap,
    GapStatus,
    Regulation,
)

logger = logging.getLogger(__name__)


async def compute_module_scores(db: AsyncSession) -> Dict[str, float]:
    """Compute per-module compliance scores.

    Returns:
        Dict mapping module name → score (0-100).
        Example: {"Pharmacy": 87.5, "IDT": 92.0, "Care Plan": 78.3}
    """
    result = await db.execute(select(ComplianceGap))
    gaps = result.scalars().all()

    # Tally per module
    module_totals: Dict[str, int] = defaultdict(int)
    module_resolved: Dict[str, int] = defaultdict(int)

    for gap in gaps:
        modules = gap.affected_modules or ["General"]
        resolved = gap.status in (GapStatus.RESOLVED, GapStatus.ACCEPTED_RISK)
        for mod in modules:
            module_totals[mod] += 1
            if resolved:
                module_resolved[mod] += 1

    scores = {}
    for mod, total in module_totals.items():
        resolved = module_resolved.get(mod, 0)
        scores[mod] = round((resolved / total) * 100, 1) if total > 0 else 100.0

    return scores


async def compute_overall_score(db: AsyncSession) -> float:
    """Compute a single overall compliance score."""
    result = await db.execute(
        select(func.count()).select_from(ComplianceGap)
    )
    total = result.scalar() or 0

    if total == 0:
        return 100.0

    result = await db.execute(
        select(func.count())
        .select_from(ComplianceGap)
        .where(ComplianceGap.status.in_([GapStatus.RESOLVED.value, GapStatus.ACCEPTED_RISK.value]))
    )
    resolved = result.scalar() or 0

    return round((resolved / total) * 100, 1)


async def aggregate_week_metrics(
    db: AsyncSession,
    week_start: datetime,
    week_end: datetime,
) -> dict:
    """Aggregate compliance metrics for a given week.

    Returns:
        Dict with new_regulations, gaps_identified, gaps_resolved, compliance_score.
    """
    # New regulations ingested this week
    new_regs_result = await db.execute(
        select(func.count())
        .select_from(Regulation)
        .where(
            and_(
                Regulation.ingested_at >= week_start,
                Regulation.ingested_at < week_end,
            )
        )
    )
    new_regulations = new_regs_result.scalar() or 0

    # Gaps identified this week
    gaps_identified_result = await db.execute(
        select(func.count())
        .select_from(ComplianceGap)
        .where(
            and_(
                ComplianceGap.created_at >= week_start,
                ComplianceGap.created_at < week_end,
            )
        )
    )
    gaps_identified = gaps_identified_result.scalar() or 0

    # Gaps resolved this week
    gaps_resolved_result = await db.execute(
        select(func.count())
        .select_from(ComplianceGap)
        .where(
            and_(
                ComplianceGap.updated_at >= week_start,
                ComplianceGap.updated_at < week_end,
                ComplianceGap.status.in_([
                    GapStatus.RESOLVED.value,
                    GapStatus.ACCEPTED_RISK.value,
                ]),
            )
        )
    )
    gaps_resolved = gaps_resolved_result.scalar() or 0

    # Overall compliance score
    compliance_score = await compute_overall_score(db)

    return {
        "new_regulations": new_regulations,
        "gaps_identified": gaps_identified,
        "gaps_resolved": gaps_resolved,
        "compliance_score": compliance_score,
    }


async def build_gaps_summary(db: AsyncSession, limit: int = 20) -> str:
    """Build a text summary of active gaps for the LLM prompt."""
    result = await db.execute(
        select(ComplianceGap)
        .where(ComplianceGap.status.in_([
            GapStatus.IDENTIFIED.value,
            GapStatus.IN_PROGRESS.value,
        ]))
        .order_by(ComplianceGap.created_at.desc())
        .limit(limit)
    )
    gaps = result.scalars().all()

    if not gaps:
        return "No active compliance gaps."

    lines = []
    for g in gaps:
        modules = ", ".join(g.affected_modules or ["General"])
        lines.append(
            f"- [{g.severity.upper() if hasattr(g.severity, 'upper') else g.severity}] "
            f"{g.title} (modules: {modules}, status: {g.status})"
        )
    return "\n".join(lines)


async def build_deadlines_summary(db: AsyncSession, days_ahead: int = 30) -> str:
    """Build a text summary of upcoming regulation deadlines."""
    cutoff = datetime.utcnow() + timedelta(days=days_ahead)
    result = await db.execute(
        select(Regulation)
        .where(
            and_(
                Regulation.effective_date.isnot(None),
                Regulation.effective_date <= cutoff.date(),
                Regulation.effective_date >= datetime.utcnow().date(),
            )
        )
        .order_by(Regulation.effective_date)
        .limit(10)
    )
    regs = result.scalars().all()

    if not regs:
        return "No upcoming deadlines in the next 30 days."

    lines = []
    for r in regs:
        lines.append(f"- {r.title} — effective {r.effective_date.isoformat()}")
    return "\n".join(lines)

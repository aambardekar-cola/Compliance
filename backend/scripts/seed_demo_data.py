import asyncio
import logging
import uuid
from datetime import datetime, timedelta

from shared.db import get_engine, Base
from shared.models import (
    Tenant,
    Regulation,
    GapAnalysis,
    GapSeverity,
    GapStatus,
    RegulationStatus,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

async def seed_demo_data():
    """Seeds the database with realistic mock data for the demo environment."""
    logger.info("Seeding demo environment with mock data...")
    engine = await get_engine()

    async with AsyncSession(engine) as session:
        # Check if we already seeded to avoid duplication
        existing = await session.execute(select(Tenant).where(Tenant.name == "Sunrise PACE"))
        if existing.scalar_one_or_none():
            logger.info("Demo data already exists. Skipping seeding.")
            return

        logger.info("Creating Tenants...")
        tenant = Tenant(
            id=uuid.UUID("68b32363-2287-4632-8406-8b3236322874"),
            name="Sunrise PACE",
            descope_tenant_id="tenant-custom-001",
            settings={"audit_logs": True, "jira_integration": True},
        )
        session.add(tenant)

        logger.info("Creating Regulations...")
        reg_cms = Regulation(
            title="CMS PACE Manual Chapter 5",
            source="cms.gov",
            version="October 2024",
            summary="Requirements for Quality Improvement Programs in PACE organizations.",
            url="https://www.cms.gov/Regulations-and-Guidance/Guidance/Manuals/Downloads/pace111c05.pdf",
            effective_date=datetime.now().date() - timedelta(days=90),
        )
        reg_hipaa = Regulation(
            title="HIPAA Security Rule",
            source="hhs.gov",
            version="2013 Omnibus",
            summary="National standards to protect individuals' electronic personal health information.",
            url="https://www.hhs.gov/hipaa/for-professionals/security/index.html",
            effective_date=datetime.fromisoformat("2013-03-26").date(),
        )
        session.add_all([reg_cms, reg_hipaa])
        await session.flush()  # Flush to get regulation IDs

        logger.info("Creating Gaps...")
        
        # Gap 1: CMS Quality Improvement
        gap1 = GapAnalysis(
            regulation_id=reg_cms.id,
            title="Missing automated quality metrics reporting",
            description="The current EHR system does not automatically aggregate quality improvement metrics as required by the new CMS guidance.",
            status=GapStatus.IDENTIFIED,
            severity=GapSeverity.HIGH,
            jira_epic_key="PCO-105",
        )
        
        # Gap 2: HIPAA Audit Logging
        gap2 = GapAnalysis(
            regulation_id=reg_hipaa.id,
            title="Incomplete PHI access logs",
            description="Access to specific participant encounter notes is not being reliably recorded in the central audit log.",
            status=GapStatus.IN_PROGRESS,
            severity=GapSeverity.CRITICAL,
            jira_epic_key="PCO-210",
        )
        session.add_all([gap1, gap2])

        await session.commit()
        logger.info("Demo mock data successfully seeded!")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_demo_data())

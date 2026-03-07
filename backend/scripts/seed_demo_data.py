import asyncio
import logging
from datetime import datetime, timedelta

from backend.shared.db import get_engine, Base
from backend.shared.models import (
    Tenant,
    Regulation,
    RegulationSection,
    ComplianceGap,
    GapTask,
    JiraEpic,
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
            id="tenant-custom-001",
            name="Sunrise PACE",
            domain="sunrisepace.org",
            subscription_tier="enterprise",
            features={"audit_logs": True, "jira_integration": True},
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
        await session.flush() # Flush to get regulation IDs

        logger.info("Creating Regulation Sections...")
        sec_qm = RegulationSection(
            regulation_id=reg_cms.id,
            section_number="460.130",
            title="Quality improvement plan",
            content="A PACE organization must develop, implement, maintain, and evaluate an effective, data-driven quality improvement program.",
            importance="high",
        )
        sec_audit = RegulationSection(
            regulation_id=reg_hipaa.id,
            section_number="164.312(b)",
            title="Audit controls",
            content="Implement hardware, software, and/or procedural mechanisms that record and examine activity in information systems that contain or use electronic protected health information.",
            importance="critical",
        )
        session.add_all([sec_qm, sec_audit])
        await session.flush()

        logger.info("Creating Compliance Gaps & Tasks...")
        
        # Gap 1: CMS Quality Improvement
        gap1 = ComplianceGap(
            tenant_id=tenant.id,
            section_id=sec_qm.id,
            title="Missing automated quality metrics reporting",
            description="The current EHR system does not automatically aggregate quality improvement metrics as required by the new CMS guidance.",
            status="open",
            severity="high",
            identified_date=datetime.now().date() - timedelta(days=15),
            jira_issue_key="PCO-105",
            gitlab_issue_url="https://gitlab.com/collabrios/pco-ehr/-/issues/105",
        )
        session.add(gap1)
        await session.flush()

        task1 = GapTask(
            gap_id=gap1.id,
            title="Implement dashboard for QM metrics",
            description="Create a new dashboard view that aggregates and averages participant assessment scores.",
            status="in_progress",
            assigned_to="dev_team_alpha",
            due_date=datetime.now().date() + timedelta(days=14),
        )
        task2 = GapTask(
            gap_id=gap1.id,
            title="Update database schema for QM",
            description="Add tables for longitudinal quality tracking.",
            status="completed",
            assigned_to="db_admin",
            due_date=datetime.now().date() - timedelta(days=2),
        )
        session.add_all([task1, task2])

        # Gap 2: HIPAA Audit Logging
        gap2 = ComplianceGap(
            tenant_id=tenant.id,
            section_id=sec_audit.id,
            title="Incomplete PHI access logs",
            description="Access to specific participant encounter notes is not being reliably recorded in the central audit log.",
            status="in_progress",
            severity="critical",
            identified_date=datetime.now().date() - timedelta(days=5),
            jira_issue_key="PCO-210",
        )
        session.add(gap2)
        await session.flush()

        task3 = GapTask(
            gap_id=gap2.id,
            title="Patch encounter notes API",
            description="Ensure the GET endpoint for encounter notes always calls the audit logging service.",
            status="open",
            assigned_to="backend_api_team",
            due_date=datetime.now().date() + timedelta(days=5),
        )
        session.add(task3)

        logger.info("Creating Jira Epics...")
        epic1 = JiraEpic(
            tenant_id=tenant.id,
            epic_key="PCO-100",
            summary="Q3 CMS Regulation Compliance",
            status="In Progress",
            url="https://jira.collabrios.com/browse/PCO-100",
        )
        session.add(epic1)

        await session.commit()
        logger.info("Demo mock data successfully seeded!")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_demo_data())

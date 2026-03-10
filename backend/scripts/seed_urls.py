import asyncio
import os
import sys

# Add the backend dir to the Python path so we can import models and config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from shared.config import get_settings
from shared.models import ComplianceRuleUrl
from shared.db import get_db_session, init_db

settings = get_settings()

SEED_URLS = [
    {
        "name": "eCFR Title 42, Part 460 (PACE Regulations)",
        "url": "https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-E/part-460",
        "description": "The definitive, living codified version of all Federal PACE regulations covering organization, services, and participant rights.",
    },
    {
        "name": "Federal Register: CY 2024 MA and PACE Final Rule",
        "url": "https://www.federalregister.gov/documents/2024/04/23/2024-07105/medicare-and-medicaid-programs-medicare-advantage-medicare-prescription-drug-benefit-program",
        "description": "Latest finalized regulatory changes for Medicare Advantage and PACE, including immunization and grievance updates.",
    },
    {
        "name": "CMS PACE Program Manual (All Chapters)",
        "url": "https://www.cms.gov/regulations-and-guidance/guidance/manuals/internet-only-manuals-ioms-items/cms019036",
        "description": "Official CMS guidance manual providing sub-regulatory details on operationalizing PACE requirements.",
    },
    {
        "name": "eCFR Title 45 Part 164: HIPAA Security Rule",
        "url": "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164",
        "description": "HIPAA Privacy, Security, and Breach Notification Rules from eCFR — the actual regulation text.",
    },
    {
        "name": "Federal Register: CY 2027 MA/PACE Proposed Rule",
        "url": "https://www.federalregister.gov/documents/2025/11/28/2025-21456/medicare-program-contract-year-2027-policy-and-technical-changes-to-the-medicare-advantage-program",
        "description": "Latest CY2027 Medicare Advantage and PACE proposed rule covering policy and technical changes.",
    },
    {
        "name": "CMS.gov: PACE Program Overview",
        "url": "https://www.cms.gov/medicare/health-plans/pace/overview",
        "description": "CMS PACE program overview page with quality requirements and program information.",
    }
]

async def seed_data():
    # Reset cached engine/session to avoid event loop conflicts
    # (the Lambda handler creates these on a different loop)
    import shared.db as db_module
    db_module._engine = None
    db_module._session_factory = None

    # Ensure all tables are created (idempotent)
    await init_db()
    
    async with get_db_session() as session:
        print("Starting seed of ComplianceRuleUrl...")
        for item in SEED_URLS:
            stmt = select(ComplianceRuleUrl).where(ComplianceRuleUrl.url == item["url"])
            result = await session.execute(stmt)
            existing = result.scalars().first()
            
            if existing:
                print(f"Skipping already seeded URL: {item['url']}")
                continue
                
            rule = ComplianceRuleUrl(
                name=item["name"],
                url=item["url"],
                description=item["description"],
                is_active=True
            )
            session.add(rule)
        
        await session.commit()
        print("Seed completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed_data())

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
        "name": "HHS/OCR: HIPAA Security Rule Requirements",
        "url": "https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html",
        "description": "Federal standards for protecting electronic protected health information (ePHI).",
    },
    {
        "name": "Medicaid.gov: PACE Program Overview & Memos",
        "url": "https://www.medicaid.gov/medicaid/long-term-services-supports/program-all-inclusive-care-elderly/index.html",
        "description": "Central repository for State/Federal Medicaid PACE coordination, eligibility guidance, and official memos.",
    },
    {
        "name": "CMS.gov: PACE Quality Reporting Requirements",
        "url": "https://www.cms.gov/medicare/quality/pace-quality-reporting",
        "description": "Official requirements for PACE quality data submission and performance monitoring.",
    }
]

async def seed_data():
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

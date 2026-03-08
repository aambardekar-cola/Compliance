import asyncio
import os
import sys

# Add the backend dir to the Python path so we can import models and config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from shared.config import get_settings
from shared.models import ComplianceRuleUrl

settings = get_settings()

# Re-use the engine setup from api/main.py
engine = create_async_engine(settings.DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

SEED_URLS = [
    {
        "name": "eCFR Title 42, Part 460 (PACE Regulations)",
        "url": "https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-E/part-460",
        "description": "The definitive, living codified version of all Federal PACE regulations.",
    },
    {
        "name": "Federal Register: CY 2024 MA and PACE Final Rule",
        "url": "https://www.federalregister.gov/documents/2024/04/23/2024-07105/medicare-and-medicaid-programs-medicare-advantage-medicare-prescription-drug-benefit-program",
        "description": "Contains the latest finalized changes for MA and PACE, including immunization and grievance updates.",
    },
    {
        "name": "CMS/Medicaid Official PACE Program Overview",
        "url": "https://www.medicaid.gov/medicaid/long-term-services-supports/program-all-inclusive-care-elderly/index.html",
        "description": "Contains critical sub-regulatory guidance, application updates, and CMS memos.",
    }
]

async def seed_data():
    async with AsyncSessionLocal() as session:
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

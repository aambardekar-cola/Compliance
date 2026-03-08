import asyncio
import json
import logging
import os
from uuid import uuid4, UUID
from unittest.mock import patch, MagicMock
from io import BytesIO

from sqlalchemy import select

from shared.db import get_engine, Base, get_db_session
from shared.models import ScrapedContent, ComplianceRuleUrl, ComplianceGap

# Set dummy AWS region before importing handler so boto3 client init doesn't crash locally
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
from analysis.handler import process_scraped_content

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock Federal Register Text - Contains both irrelevant filler and a specific PACE requirement.
MOCK_TEXT = """
DEPARTMENT OF HEALTH AND HUMAN SERVICES
Centers for Medicare & Medicaid Services
42 CFR Part 460
[CMS-4201-F]
RIN 0938-AV16

Medicare and Medicaid Programs; Contract Year 2026 Policy and Technical Changes to the Medicare Advantage Program, Medicare Prescription Drug Benefit Program, and Medicare Cost Plan Program.

This section provides general background on the statutory authority for the PACE program.
Section 1894 of the Social Security Act establishes the Medicare PACE program.
Section 1934 of the Act establishes the Medicaid PACE program.
We received 14 public comments regarding this general authority.

Subpart E - PACE Administrative Requirements

We are finalizing new rules for the Interdisciplinary Team (IDT).
Previously, the IDT was required to meet in person to discuss any changes to a participant's care plan.
However, due to telehealth expansion, we are modifying § 460.104.
Effective January 1, 2026, the primary care provider and the registered nurse must evaluate the participant in person, but other members of the IDT (such as the pharmacist, social worker, or physical therapist) may attend the care planning meetings virtually via telecommunications technology.
The PACE organization must document the reason for virtual attendance in the participant's medical record.
Failure to properly document virtual IDT attendance will result in a compliance deficiency during the next CMS audit.
"""

@patch('analysis.handler.boto_client')
async def run_test(mock_boto):
    """Create mock data, run the AI extraction, and print the results."""
    logger.info("Initializing Test Database...")
    
    # Mock Haiku response (YES)
    haiku_response = {
        "content": [{"text": "YES"}]
    }
    
    # Mock Sonnet response (JSON gaps)
    sonnet_response = {
        "content": [{"text": json.dumps([{
            "title": "Mock IDT Virtual Attendance Requirement",
            "description": "Effective Jan 1, 2026, IDT members may attend virtually, but virtual attendance must be documented.",
            "severity": "HIGH",
            "affected_modules": ["Interdisciplinary Team (IDT)", "Care Planning"],
            "is_new_requirement": True
        }])}]
    }
    
    # Set up the mock returns
    def invoke_model_side_effect(*args, **kwargs):
        model_id = kwargs.get('modelId', '')
        if 'haiku' in model_id:
            body = MagicMock()
            body.read.return_value = json.dumps(haiku_response).encode('utf-8')
            return {"body": body}
        else:
            body = MagicMock()
            body.read.return_value = json.dumps(sonnet_response).encode('utf-8')
            return {"body": body}
            
    mock_boto.invoke_model.side_effect = invoke_model_side_effect
    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with get_db_session() as session:
        # Create a mock URL and Scraped Content
        url = ComplianceRuleUrl(
            name="Mock 2026 PACE Final Rule",
            url="https://mock.gov",
            is_active=True
        )
        session.add(url)
        await session.flush()
        
        content = ScrapedContent(
            url_id=url.id,
            content_text=MOCK_TEXT,
            content_hash="mockhash123",
            is_processed=False
        )
        session.add(content)
        await session.flush()
        
        content_id = str(content.id)
        await session.commit()
        
    logger.info(f"Created Mock ScrapedContent {content_id}. Triggering AI Analysis Engine...")
    
    # Run the hybrid Bedrock pipeline
    await process_scraped_content(UUID(content_id))
    
    logger.info("\nAI Analysis Complete. Retrieving Results from Database...")
    
    # Verify the output
    async with get_db_session() as session:
        result = await session.execute(
            select(ComplianceGap).where(ComplianceGap.scraped_content_id == content.id)
        )
        gaps = result.scalars().all()
        
        print("\n" + "="*80)
        print(f"TEST RESULTS: Found {len(gaps)} Compliance Gaps")
        print("="*80)
        
        for gap in gaps:
            print(f"\nTitle: {gap.title}")
            print(f"Severity: {gap.severity.name if gap.severity else 'None'}")
            print(f"New Requirement: {gap.is_new_requirement}")
            print(f"Target PCO Modules: {', '.join(gap.affected_modules)}")
            print(f"Description:\n{gap.description}")
            print("-" * 80)
            
        return len(gaps) > 0

if __name__ == "__main__":
    success = asyncio.run(run_test())
    if success:
        logger.info("Test completed successfully! The hybrid AI engine correctly extracted rules.")
    else:
        logger.error("Test failed. No gaps were extracted.")

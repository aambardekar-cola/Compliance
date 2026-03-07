"""Lambda handler for regulatory ingestion pipeline."""
import asyncio
import json
import logging
from datetime import datetime

import boto3
from sqlalchemy import select

from shared.config import get_settings
from shared.db import get_db_session
from shared.models import Regulation, RegulationStatus
from ingestion.sources.federal_register import FederalRegisterSource
from ingestion.sources.cms_gov import CMSGovSource
from ingestion.relevance import score_relevance

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Minimum relevance score to keep a regulation
RELEVANCE_THRESHOLD = 0.3


async def run_ingestion(event: dict = None):
    """Main ingestion pipeline: fetch → score → store → queue."""
    settings = get_settings()
    logger.info("Starting regulatory ingestion pipeline")

    # Initialize sources
    sources = [
        FederalRegisterSource(),
        CMSGovSource(),
    ]

    all_regulations = []
    for source in sources:
        try:
            regs = await source.fetch_latest()
            all_regulations.extend(regs)
            logger.info(f"Source '{source.source_name}' returned {len(regs)} documents")
        except Exception as e:
            logger.error(f"Source '{source.source_name}' failed: {e}")

    if not all_regulations:
        logger.info("No new regulations found")
        return {"statusCode": 200, "body": "No new regulations"}

    # Process and store each regulation
    new_count = 0
    updated_count = 0

    async with get_db_session() as session:
        for raw_reg in all_regulations:
            try:
                # Check if already exists (dedup by source + source_id)
                existing = await session.execute(
                    select(Regulation).where(
                        Regulation.source == raw_reg.source,
                        Regulation.source_id == raw_reg.source_id,
                    )
                )
                existing_reg = existing.scalar_one_or_none()

                # Score relevance using LLM
                analysis = await score_relevance(raw_reg)
                relevance_score = analysis.get("relevance_score", 0.0)

                # Skip low-relevance regulations
                if relevance_score < RELEVANCE_THRESHOLD:
                    logger.debug(
                        f"Skipping '{raw_reg.title[:60]}' "
                        f"(relevance={relevance_score:.2f})"
                    )
                    continue

                # Determine status from document_type
                status_map = {
                    "proposed_rule": RegulationStatus.PROPOSED,
                    "final_rule": RegulationStatus.FINAL_RULE,
                    "notice": RegulationStatus.PROPOSED,
                    "guidance": RegulationStatus.EFFECTIVE,
                    "legislation": RegulationStatus.PROPOSED,
                }
                status = status_map.get(raw_reg.document_type, RegulationStatus.PROPOSED)

                # Check if comment period is active
                if raw_reg.comment_deadline and raw_reg.comment_deadline > datetime.utcnow().date():
                    status = RegulationStatus.COMMENT_PERIOD

                if existing_reg:
                    # Update existing regulation
                    existing_reg.ai_analysis = analysis
                    existing_reg.relevance_score = relevance_score
                    existing_reg.affected_areas = analysis.get("affected_areas", [])
                    existing_reg.key_requirements = analysis.get("key_requirements", [])
                    existing_reg.summary = analysis.get("summary", raw_reg.summary)
                    existing_reg.status = status
                    updated_count += 1
                else:
                    # Create new regulation
                    regulation = Regulation(
                        source=raw_reg.source,
                        source_id=raw_reg.source_id,
                        title=raw_reg.title,
                        summary=analysis.get("summary", raw_reg.summary),
                        raw_content=raw_reg.content,
                        source_url=raw_reg.source_url,
                        ai_analysis=analysis,
                        relevance_score=relevance_score,
                        affected_areas=analysis.get("affected_areas", []),
                        key_requirements=analysis.get("key_requirements", []),
                        status=status,
                        effective_date=raw_reg.effective_date,
                        comment_deadline=raw_reg.comment_deadline,
                        published_date=raw_reg.published_date,
                        cfr_references=raw_reg.cfr_references,
                        agencies=raw_reg.agencies,
                        document_type=raw_reg.document_type,
                    )
                    session.add(regulation)
                    new_count += 1

                    # Queue for downstream processing (gap analysis)
                    if settings.analysis_queue_url:
                        await _queue_for_analysis(
                            settings.analysis_queue_url,
                            str(regulation.id),
                            raw_reg.title,
                        )

            except Exception as e:
                logger.error(f"Error processing regulation '{raw_reg.title[:60]}': {e}")

    result = {
        "statusCode": 200,
        "body": json.dumps({
            "fetched": len(all_regulations),
            "new": new_count,
            "updated": updated_count,
        }),
    }
    logger.info(f"Ingestion complete: {result['body']}")
    return result


async def _queue_for_analysis(queue_url: str, regulation_id: str, title: str):
    """Send a regulation to the SQS analysis queue."""
    try:
        sqs = boto3.client("sqs")
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({
                "regulation_id": regulation_id,
                "title": title,
                "action": "gap_analysis",
            }),
        )
        logger.info(f"Queued regulation '{title[:60]}' for gap analysis")
    except Exception as e:
        logger.error(f"Failed to queue for analysis: {e}")


def handler(event, context):
    """AWS Lambda entry point."""
    return asyncio.get_event_loop().run_until_complete(run_ingestion(event))

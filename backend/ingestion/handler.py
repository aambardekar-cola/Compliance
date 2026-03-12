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

import os

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Datadog APM — conditional import for custom spans
_tracer = None
if os.environ.get("DD_TRACE_ENABLED") == "true":
    try:
        from ddtrace import tracer as _tracer  # noqa: F811
    except ImportError:
        pass

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
        src_span = _tracer.trace(
            "ingestion.fetch_source",
            service="pco-compliance-pipeline",
            resource=source.source_name,
        ) if _tracer else None
        try:
            regs = await source.fetch_latest()
            all_regulations.extend(regs)
            logger.info(f"Source '{source.source_name}' returned {len(regs)} documents")
            if src_span:
                src_span.set_metric("ingestion.documents_found", len(regs))
        except Exception as e:
            logger.error(f"Source '{source.source_name}' failed: {e}")
            if src_span:
                src_span.set_exc_info(type(e), e, e.__traceback__)
        finally:
            if src_span:
                src_span.finish()

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
                rel_span = _tracer.trace(
                    "bedrock.score_relevance",
                    service="pco-compliance-pipeline",
                    resource=raw_reg.title[:80] if raw_reg.title else "unknown",
                ) if _tracer else None
                try:
                    analysis = await score_relevance(raw_reg)
                    relevance_score = analysis.get("relevance_score", 0.0)
                    if rel_span:
                        rel_span.set_metric("ingestion.relevance_score", relevance_score)
                        rel_span.set_tag("ingestion.source", raw_reg.source)
                except Exception as rel_err:
                    if rel_span:
                        rel_span.set_exc_info(type(rel_err), rel_err, rel_err.__traceback__)
                    raise
                finally:
                    if rel_span:
                        rel_span.finish()

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
    run_span = _tracer.trace(
        "ingestion.run",
        service="pco-compliance-pipeline",
        resource="scheduled_ingestion",
    ) if _tracer else None

    try:
        result = asyncio.get_event_loop().run_until_complete(run_ingestion(event))
        if run_span:
            import json as _json
            body = _json.loads(result.get("body", "{}"))
            run_span.set_tag("ingestion.status", "success")
            run_span.set_metric("ingestion.fetched", body.get("fetched", 0))
            run_span.set_metric("ingestion.new", body.get("new", 0))
            run_span.set_metric("ingestion.updated", body.get("updated", 0))
        return result
    except Exception as e:
        if run_span:
            run_span.set_exc_info(type(e), e, e.__traceback__)
            run_span.set_tag("ingestion.status", "error")
        raise
    finally:
        if run_span:
            run_span.finish()

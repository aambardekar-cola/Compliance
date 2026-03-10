"""Lambda handler for AI gap analysis using AWS Bedrock.

Phase 2: Two-stage extraction pipeline.
  Stage 1 — Extract Regulations from raw text (title, CFR citation, affected areas)
  Stage 2 — Identify Compliance Gaps per regulation (PACE-specific gaps)
"""
import asyncio
import json
import os
import hashlib
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta

import boto3
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from shared.db import get_db_session
from shared.models import (
    ScrapedContent, ComplianceGap, Regulation,
    GapSeverity, GapStatus, AffectedLayer, RegulationStatus,
    PipelineRun, PipelineRunType, PipelineRunStatus,
    AdminNotification, NotificationType,
)
from shared.logging import get_pipeline_logger

logger = get_pipeline_logger("analysis")

# Hybrid Bedrock Architecture: Haiku for filtering, Sonnet for deep extraction
HAIKU_MODEL_ID = os.environ.get(
    "BEDROCK_HAIKU_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)
SONNET_MODEL_ID = os.environ.get(
    "BEDROCK_SONNET_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
)
from botocore.config import Config as BotoConfig
boto_client = boto3.client(
    "bedrock-runtime",
    config=BotoConfig(read_timeout=300, retries={"max_attempts": 2})
)

# Max chars to send to Bedrock in a single request (~50K chars ≈ ~15K tokens)
MAX_CONTENT_CHARS = 50000
# Max chunks to process per Lambda invocation (prevents timeout; resumes on next trigger)
MAX_CHUNKS_PER_RUN = int(os.environ.get("MAX_CHUNKS_PER_RUN", "10"))

# Canonical list of PCO modules for consistent tagging
PCO_MODULES = [
    "IDT", "Care Plan", "Pharmacy", "Enrollment", "Claims",
    "Transportation", "Quality", "Billing", "Authorization",
    "Member Services", "Provider Network", "Reporting",
    "Administration",
]

# ---------- PROMPTS ----------

REGULATION_EXTRACTION_PROMPT = """
You are an expert PACE (Programs of All-Inclusive Care for the Elderly) compliance officer.
PaceCareOnline (PCO) is a PACE EHR software platform with these core modules:
""" + ", ".join(PCO_MODULES) + """

I will provide a chunk of raw legal text from the Federal Register or eCFR.
Your job is to extract distinct REGULATORY REQUIREMENTS from the text.

For each regulation found, provide:
- "title": A clear, concise title of the regulatory requirement (max 200 chars)
- "summary": 2-3 sentence summary of what the regulation requires
- "cfr_citation": The CFR citation if available (e.g. "42 CFR §460.102"), or "" if none
- "affected_areas": A list of PCO modules this regulation impacts. ONLY use values from: """ + json.dumps(PCO_MODULES) + """
- "effective_date": The effective date in ISO format (YYYY-MM-DD) if mentioned, or null
- "document_type": One of: "proposed_rule", "final_rule", "guidance", "notice"
- "key_requirements": A list of 1-3 specific actionable requirements (strings)

Rules:
- Each regulation should be a DISTINCT regulatory requirement, not a restatement
- If the text discusses multiple separate requirements, extract each as its own regulation
- If no actionable regulations are found, return an empty array []
- Return ONLY valid JSON array

Output format: [{"title": "...", "summary": "...", ...}, ...]
"""

GAP_IDENTIFICATION_PROMPT = """
You are an expert PACE compliance gap analyst for PaceCareOnline (PCO), a PACE EHR platform.
PCO modules: """ + ", ".join(PCO_MODULES) + """

Given a specific regulatory requirement, identify compliance GAPS — places where a PACE
organization's EHR software might NOT meet this requirement.

For each gap, provide:
- "title": A clear, actionable title describing the gap (max 200 chars)
- "description": Detailed explanation of what needs to change
- "severity": One of: "CRITICAL", "HIGH", "MEDIUM", "LOW"
- "affected_modules": PCO modules affected. ONLY use values from: """ + json.dumps(PCO_MODULES) + """
- "affected_layer": Where the fix is needed. One of: "frontend", "backend", "both", "unknown"
- "is_new_requirement": true if this is a new requirement, false if restated

Rules:
- Focus on actionable gaps that require software changes
- If the regulation is purely administrative (no software impact), return an empty array []
- Return ONLY valid JSON array

Output format: [{"title": "...", "description": "...", ...}, ...]
"""

# Legacy prompt kept for reference (Phase 1.5 single-stage extraction)
SYSTEM_PROMPT = REGULATION_EXTRACTION_PROMPT


async def invoke_bedrock(model_id: str, system: str, prompt: str, max_tokens: int = 4096) -> str:
    """Helper to invoke AWS Bedrock Claude 3 models."""
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": 0.1,
        "system": system,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    response = boto_client.invoke_model(
        modelId=model_id,
        body=json.dumps(body)
    )
    response_body = json.loads(response.get("body").read().decode("utf-8"))
    return response_body.get("content", [])[0].get("text", "")


async def filter_relevant_content(text: str) -> bool:
    """Pass 1: Haiku Filter - determines if content is relevant.
    
    Uses a truncated sample for large documents to stay within context limits.
    """
    await logger.info("Executing Pass 1 (Haiku Filtering)...")
    sample = text[:MAX_CONTENT_CHARS] if len(text) > MAX_CONTENT_CHARS else text
    filter_prompt = f"Does the following regulatory text contain any actionable compliance requirements, changes, or mandates that would affect a PACE organization? Respond with ONLY the word YES or NO. Do not explain.\n\n<TEXT>\n{sample}\n</TEXT>"
    filter_system = "You are a fast legal filter. You only respond with YES or NO."
    
    filter_result = await invoke_bedrock(model_id=HAIKU_MODEL_ID, system=filter_system, prompt=filter_prompt, max_tokens=10)
    
    return "YES" in filter_result.upper()


def chunk_text(text: str, chunk_size: int = MAX_CONTENT_CHARS) -> List[str]:
    """Split text into chunks, breaking on paragraph boundaries."""
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    while text:
        if len(text) <= chunk_size:
            chunks.append(text)
            break
        split_at = text.rfind("\n\n", 0, chunk_size)
        if split_at == -1:
            split_at = text.rfind("\n", 0, chunk_size)
        if split_at == -1:
            split_at = chunk_size
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    return chunks


def parse_json_response(raw: str) -> list:
    """Safely parse LLM JSON output, stripping markdown fences."""
    if "```json" in raw:
        raw = raw.split("```json")[-1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[-1].split("```")[0].strip()
    
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict):
            # Handle {"regulations": [...]} or {"gaps": [...]} wrappers
            for key in ("regulations", "gaps", "items", "results"):
                if key in parsed and isinstance(parsed[key], list):
                    return parsed[key]
            return [parsed]  # Single object → wrap in list
        return []
    except json.JSONDecodeError:
        return []


def safe_severity(val: Any) -> GapSeverity:
    """Parse severity with defensive fallback to MEDIUM."""
    try:
        return GapSeverity(str(val or "medium").lower())
    except (ValueError, KeyError):
        return GapSeverity.MEDIUM


def safe_affected_layer(val: Any) -> AffectedLayer:
    """Parse affected_layer with defensive fallback to UNKNOWN."""
    try:
        return AffectedLayer(str(val or "unknown").lower())
    except (ValueError, KeyError):
        return AffectedLayer.UNKNOWN


async def process_scraped_content(content_id: UUID) -> bool:
    """Run the two-stage AI analysis on a piece of scraped content.
    
    Stage 1: Extract Regulations from each chunk
    Stage 2: Identify Compliance Gaps per regulation
    
    Supports incremental processing: progress is tracked per-chunk and
    processing resumes from where it left off on retry.
    """
    await logger.info(f"Starting AI analysis for ScrapedContent {content_id}")
    
    async with get_db_session() as session:
        # 1. Fetch the content
        result = await session.execute(
            select(ScrapedContent)
            .options(joinedload(ScrapedContent.rule_url))
            .where(ScrapedContent.id == content_id)
        )
        content = result.scalar_one_or_none()
        
        if not content:
            await logger.error(f"ScrapedContent {content_id} not found")
            return False
            
        if content.is_processed:
            await logger.warning(f"ScrapedContent {content_id} already processed")
            return True

        try:
            # Pass 1: Filtering (Haiku) — skip if we already have progress
            if not content.chunks_processed or content.chunks_processed == 0:
                await logger.info(f"Pass 1: Filtering content with Claude 3 Haiku", {"length": len(content.content_text)})
                is_relevant = await filter_relevant_content(content.content_text)
                
                if not is_relevant:
                    await logger.info(f"Content identified as irrelevant, skipping analysis")
                    content.is_processed = True
                    await session.commit()
                    return True
            else:
                await logger.info(f"Resuming from chunk {content.chunks_processed + 1}")

            # Pass 2: Two-stage chunked extraction with per-chunk persistence
            await logger.info(f"Pass 2: Two-stage extraction (Regulations → Gaps)")
            chunks = chunk_text(content.content_text)
            total = len(chunks)
            start_chunk = content.chunks_processed or 0
            
            content.total_chunks = total
            await session.commit()
            
            end_chunk = min(start_chunk + MAX_CHUNKS_PER_RUN, total)
            await logger.info(f"Processing chunks {start_chunk + 1}-{end_chunk}/{total} (max {MAX_CHUNKS_PER_RUN}/run)")

            # Get source URL from the parent ComplianceRuleUrl for regulation metadata
            source_url = ""
            try:
                if content.rule_url:
                    source_url = content.rule_url.url or ""
            except Exception:
                pass  # Relationship not loaded — not critical
            
            for i in range(start_chunk, end_chunk):
                chunk = chunks[i]
                chunk_hash = hashlib.sha256(chunk.encode()).hexdigest()[:16]
                await logger.info(f"Chunk {i+1}/{total} ({len(chunk)} chars)")
                
                # --- STAGE 1: Extract Regulations from this chunk ---
                reg_prompt = f"Extract all distinct regulatory requirements from the following text:\n\n<TEXT>\n{chunk}\n</TEXT>"
                raw_regs = await invoke_bedrock(
                    model_id=SONNET_MODEL_ID,
                    system=REGULATION_EXTRACTION_PROMPT,
                    prompt=reg_prompt,
                    max_tokens=8192
                )
                reg_list = parse_json_response(raw_regs)
                
                if not reg_list:
                    await logger.info(f"Chunk {i+1}: no regulations found, skipping")
                    content.chunks_processed = i + 1
                    await session.commit()
                    continue
                
                await logger.info(f"Chunk {i+1}: found {len(reg_list)} regulation(s)")
                
                chunk_regulations = []
                for reg_dict in reg_list:
                    if not isinstance(reg_dict, dict):
                        continue
                    
                    title = str(reg_dict.get("title", ""))[:1000]
                    if not title:
                        continue
                    
                    cfr = str(reg_dict.get("cfr_citation", ""))[:200]
                    doc_hash = hashlib.sha256(f"{cfr}|{title}".encode()).hexdigest()
                    
                    # Dedup: check by chunk hash first
                    existing = await session.execute(
                        select(Regulation).where(
                            Regulation.document_chunk_hash == doc_hash
                        )
                    )
                    existing_reg = existing.scalar_one_or_none()
                    
                    if existing_reg:
                        await logger.info(f"  Regulation already exists (hash): {title[:80]}")
                        chunk_regulations.append(existing_reg)
                        continue
                    
                    # Dedup: also check by (source, source_id) unique constraint
                    if cfr:
                        existing_by_src = await session.execute(
                            select(Regulation).where(
                                Regulation.source == "federal_register",
                                Regulation.source_id == cfr,
                            )
                        )
                        existing_src_reg = existing_by_src.scalar_one_or_none()
                        if existing_src_reg:
                            await logger.info(f"  Regulation already exists (source_id): {cfr}")
                            chunk_regulations.append(existing_src_reg)
                            continue
                    
                    # Parse effective_date safely
                    eff_date = None
                    raw_date = reg_dict.get("effective_date")
                    if raw_date:
                        try:
                            eff_date = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d").date()
                        except (ValueError, TypeError):
                            pass
                    
                    # Normalize affected_areas to canonical PCO modules
                    raw_areas = reg_dict.get("affected_areas", [])
                    if not isinstance(raw_areas, list):
                        raw_areas = []
                    affected_areas = [a for a in raw_areas if a in PCO_MODULES]
                    
                    try:
                        new_reg = Regulation(
                            scraped_content_id=content.id,
                            source="federal_register",
                            source_id=cfr or None,
                            title=title,
                            summary=str(reg_dict.get("summary", ""))[:5000],
                            source_url=source_url,
                            relevance_score=0.8,  # High relevance — passed Haiku filter
                            affected_areas=affected_areas,
                            key_requirements=reg_dict.get("key_requirements", []),
                            status=RegulationStatus.PROPOSED,
                            effective_date=eff_date,
                            document_type=str(reg_dict.get("document_type", "final_rule"))[:100],
                            cfr_references=[cfr] if cfr else [],
                            agencies=["CMS"],
                            document_chunk_hash=doc_hash,
                        )
                        session.add(new_reg)
                        await session.flush()  # Get the ID
                        chunk_regulations.append(new_reg)
                        await logger.info(f"  + Regulation saved: {title[:80]}")
                    except Exception as flush_err:
                        await session.rollback()
                        await logger.error(f"  ! Regulation insert failed: {title[:80]}: {flush_err}")
                        # Try to recover by fetching the existing regulation
                        if cfr:
                            fallback = await session.execute(
                                select(Regulation).where(
                                    Regulation.source == "federal_register",
                                    Regulation.source_id == cfr,
                                )
                            )
                            fallback_reg = fallback.scalar_one_or_none()
                            if fallback_reg:
                                chunk_regulations.append(fallback_reg)
                                await logger.info(f"  ~ Recovered existing regulation: {cfr}")
                
                # --- STAGE 2: Identify Gaps per Regulation ---
                total_gaps = 0
                for reg in chunk_regulations:
                    gap_prompt = (
                        f"Given this regulatory requirement, identify compliance gaps:\n\n"
                        f"REGULATION: {reg.title}\n"
                        f"SUMMARY: {reg.summary or 'N/A'}\n"
                        f"CFR: {reg.source_id or 'N/A'}\n"
                        f"AFFECTED AREAS: {', '.join(reg.affected_areas or [])}\n"
                        f"KEY REQUIREMENTS: {json.dumps(reg.key_requirements or [])}\n"
                    )
                    
                    raw_gaps = await invoke_bedrock(
                        model_id=SONNET_MODEL_ID,
                        system=GAP_IDENTIFICATION_PROMPT,
                        prompt=gap_prompt,
                        max_tokens=4096
                    )
                    gap_list = parse_json_response(raw_gaps)
                    
                    for gap_dict in gap_list:
                        if not isinstance(gap_dict, dict):
                            continue
                        
                        gap_title = str(gap_dict.get("title", ""))[:500]
                        if not gap_title:
                            continue
                        
                        new_gap = ComplianceGap(
                            scraped_content_id=content.id,
                            regulation_id=reg.id,
                            title=gap_title,
                            description=str(gap_dict.get("description", "")),
                            severity=safe_severity(gap_dict.get("severity")),
                            status=GapStatus.IDENTIFIED,
                            affected_modules=gap_dict.get("affected_modules", []),
                            affected_layer=safe_affected_layer(gap_dict.get("affected_layer")),
                            is_new_requirement=bool(gap_dict.get("is_new_requirement", False)),
                        )
                        session.add(new_gap)
                        total_gaps += 1
                    
                if total_gaps > 0:
                    await logger.info(f"Chunk {i+1}: {len(chunk_regulations)} regs → {total_gaps} gaps saved")
                
                # Update progress and commit after each chunk
                try:
                    content.chunks_processed = i + 1
                    await session.commit()
                except Exception as commit_err:
                    await session.rollback()
                    await logger.error(f"Chunk {i+1} commit failed: {commit_err}")
                    # Re-fetch content so we can continue with next chunk
                    result = await session.execute(
                        select(ScrapedContent).where(ScrapedContent.id == content_id)
                    )
                    content = result.scalar_one_or_none()
                    if not content:
                        await logger.error(f"Lost ScrapedContent {content_id} after rollback")
                        return False
            
            # Mark as fully processed only if ALL chunks are done
            if content.chunks_processed >= total:
                content.is_processed = True
                await session.commit()
                await logger.info(f"Analysis complete for ScrapedContent {content_id} — all {total} chunks done")
            else:
                await logger.info(f"Batch done: chunks {start_chunk + 1}-{end_chunk}/{total}. Trigger again to continue.")
            return True
            
        except Exception as e:
            await logger.error(f"AI analysis failed for ScrapedContent {content_id}: {e}", exc_info=True)
            return False


async def _cleanup_stale_runs(max_age_minutes: int = 10) -> int:
    """Auto-close pipeline runs stuck at 'started' for too long (Lambda timeout)."""
    cleaned = 0
    try:
        from sqlalchemy import and_
        cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        async with get_db_session() as session:
            result = await session.execute(
                select(PipelineRun).where(
                    and_(
                        PipelineRun.status == PipelineRunStatus.STARTED,
                        PipelineRun.started_at < cutoff,
                    )
                )
            )
            stale_runs = result.scalars().all()
            for run in stale_runs:
                run.status = PipelineRunStatus.FAILED
                run.ended_at = datetime.utcnow()
                run.duration_seconds = (run.ended_at - run.started_at).total_seconds()
                run.error_message = "Auto-closed: Lambda timed out before finalization"
                cleaned += 1
            if cleaned:
                await session.commit()
                await logger.info(f"Cleaned up {cleaned} stale pipeline run(s)")
    except Exception as e:
        await logger.error(f"Failed to clean stale runs: {e}")
    return cleaned


async def _finalize_pipeline_run(
    pipeline_run_id: Optional[UUID],
    start_time: datetime,
    records_processed: int,
    total_regs: int,
    total_gaps_added: int,
    total_errors: int,
    error_messages: List[str],
) -> None:
    """Finalize a PipelineRun record and create an AdminNotification."""
    if not pipeline_run_id:
        return

    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()

    try:
        async with get_db_session() as session:
            run = await session.get(PipelineRun, pipeline_run_id)
            if not run:
                return

            run.status = (
                PipelineRunStatus.FAILED if total_errors > 0 and records_processed == 0
                else PipelineRunStatus.PARTIAL if total_errors > 0
                else PipelineRunStatus.COMPLETED
            )
            run.ended_at = end_time
            run.duration_seconds = duration
            run.chunks_processed = records_processed
            run.regulations_added = max(total_regs, 0)
            run.gaps_added = max(total_gaps_added, 0)
            run.errors_count = total_errors
            run.error_message = "; ".join(error_messages) if error_messages else None

            # Create notification
            if total_errors > 0 and records_processed == 0:
                notif_type = NotificationType.PIPELINE_FAILED
                title = "Analysis Pipeline Failed"
                message = f"Analysis failed: {'; '.join(error_messages[:3])}"
            else:
                notif_type = NotificationType.PIPELINE_COMPLETED
                title = "Analysis Pipeline Completed"
                parts = []
                if records_processed:
                    parts.append(f"{records_processed} chunk(s) processed")
                if total_regs > 0:
                    parts.append(f"{total_regs} new regulation(s)")
                if total_gaps_added > 0:
                    parts.append(f"{total_gaps_added} new gap(s)")
                if total_errors > 0:
                    parts.append(f"{total_errors} error(s)")
                message = ("Analysis completed: " + ", ".join(parts)) if parts else "Analysis completed with no changes."

            notification = AdminNotification(
                pipeline_run_id=pipeline_run_id,
                notification_type=notif_type,
                title=title,
                message=message,
                metadata_json={
                    "chunks_processed": records_processed,
                    "regulations_added": max(total_regs, 0),
                    "gaps_added": max(total_gaps_added, 0),
                    "errors": total_errors,
                    "duration_seconds": round(duration, 1),
                },
            )
            session.add(notification)
            await session.commit()
    except Exception as e:
        await logger.error(f"Failed to finalize PipelineRun: {e}")


async def run_analysis(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse SQS records and process them using the LLM logic.
    
    Creates a PipelineRun record to track this invocation,
    and an AdminNotification summarizing the results.
    Uses try/finally to ensure the run is always finalized.
    """
    start_time = datetime.utcnow()
    total_regs = 0
    total_gaps_added = 0
    total_errors = 0
    records_processed = 0
    error_messages = []
    pipeline_run_id = None

    # Step 0: Clean up any stale "started" runs from previous Lambda timeouts
    await _cleanup_stale_runs(max_age_minutes=10)

    # Step 1: Create pipeline run record
    try:
        async with get_db_session() as session:
            pipeline_run = PipelineRun(
                run_type=PipelineRunType.ANALYSIS,
                status=PipelineRunStatus.STARTED,
                started_at=start_time,
            )
            session.add(pipeline_run)
            await session.commit()
            pipeline_run_id = pipeline_run.id
    except Exception as e:
        await logger.error(f"Failed to create PipelineRun: {e}")

    # Step 2: Process SQS records — wrapped in try/finally for guaranteed finalization
    try:
        for record in event.get("Records", []):
            try:
                body = json.loads(record.get("body", "{}"))
                content_id_str = body.get("scraped_content_id")
                
                if content_id_str:
                    content_id = UUID(content_id_str)
                    # Count regulations and gaps before processing
                    pre_regs = 0
                    pre_gaps = 0
                    try:
                        async with get_db_session() as session:
                            from sqlalchemy import func as sqla_func
                            pre_regs = (await session.execute(
                                select(sqla_func.count()).select_from(Regulation)
                            )).scalar() or 0
                            pre_gaps = (await session.execute(
                                select(sqla_func.count()).select_from(ComplianceGap)
                            )).scalar() or 0
                    except Exception:
                        pass

                    success = await process_scraped_content(content_id)
                    records_processed += 1

                    # Count after processing
                    try:
                        async with get_db_session() as session:
                            from sqlalchemy import func as sqla_func
                            post_regs = (await session.execute(
                                select(sqla_func.count()).select_from(Regulation)
                            )).scalar() or 0
                            post_gaps = (await session.execute(
                                select(sqla_func.count()).select_from(ComplianceGap)
                            )).scalar() or 0
                            total_regs += (post_regs - pre_regs)
                            total_gaps_added += (post_gaps - pre_gaps)
                    except Exception:
                        pass

                    if not success:
                        total_errors += 1
                        error_messages.append(f"Content {content_id_str} failed")
                else:
                    await logger.error("SQS message missing scraped_content_id.")
                    total_errors += 1
            except Exception as e:
                await logger.error(f"Error processing SQS record: {e}", exc_info=True)
                total_errors += 1
                error_messages.append(str(e)[:200])
    finally:
        # Step 3: ALWAYS finalize the pipeline run, even on Lambda timeout
        await _finalize_pipeline_run(
            pipeline_run_id, start_time,
            records_processed, total_regs, total_gaps_added,
            total_errors, error_messages,
        )

    return {"statusCode": 200, "body": "Gap analysis complete"}


def handler(event, context):
    """AWS Lambda SQS entry point."""
    return asyncio.get_event_loop().run_until_complete(run_analysis(event))

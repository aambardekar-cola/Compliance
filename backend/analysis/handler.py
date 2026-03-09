"""Lambda handler for AI gap analysis using AWS Bedrock."""
import asyncio
import json
import os
import hashlib
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime

import boto3
from sqlalchemy import select

from shared.db import get_db_session
from shared.models import ScrapedContent, ComplianceGap, GapSeverity, GapStatus
from shared.logging import get_pipeline_logger

logger = get_pipeline_logger("analysis")

# Hybrid Bedrock Architecture: Haiku for filtering, Sonnet for deep extraction
# Use cross-region inference profiles (required for on-demand invocation)
HAIKU_MODEL_ID = "us.anthropic.claude-3-haiku-20240307-v1:0"
SONNET_MODEL_ID = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
boto_client = boto3.client("bedrock-runtime")

SYSTEM_PROMPT = """
You are an expert PACE (Programs of All-Inclusive Care for the Elderly) compliance officer.
PaceCareOnline (PCO) is a software platform managing PACE organizations. The software is divided into these core modules:
1. Care Planning
2. Interdisciplinary Team (IDT)
3. Medicare Part D / Pharmacy
4. Claims Processing
5. Participant Enrollment
6. Quality Improvement
7. Administration & Reporting

I will provide you with chunks of raw legal text from the Federal Register or eCFR.
Your job is to read the text and identify actionable compliance requirements or rule changes that would affect a PACE organization using our software.

Analyze the text and output a valid JSON array of objects. If there are no actionable gaps, output an empty array [].
For each requirement found, provide:
- "title": A short, clear title of the requirement (string, max 500 chars)
- "description": A detailed explanation of what must change (string)
- "severity": Must be exactly one of: "CRITICAL", "HIGH", "MEDIUM", "LOW"
- "affected_modules": A list of strings matching the core modules above (e.g. ["Care Planning", "IDT"])
- "is_new_requirement": Boolean (true if this is a new change, false if it's existing/restated)
- "requirement": The specific regulatory requirement text (string)
- "citation": The citation for the requirement (string)

Return ONLY valid JSON.
"""

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
    """Pass 1: Haiku Filter - determines if content is relevant."""
    await logger.info("Executing Pass 1 (Haiku Filtering)...")
    filter_prompt = f"Does the following regulatory text contain any actionable compliance requirements, changes, or mandates that would affect a PACE organization? Respond with ONLY the word YES or NO. Do not explain.\n\n<TEXT>\n{text}\n</TEXT>"
    filter_system = "You are a fast legal filter. You only respond with YES or NO."
    
    filter_result = await invoke_bedrock(model_id=HAIKU_MODEL_ID, system=filter_system, prompt=filter_prompt, max_tokens=10)
    
    return "YES" in filter_result.upper()


async def extract_compliance_gaps(text: str) -> List[Dict]:
    """Pass 2: Sonnet Extraction - extracts compliance gaps."""
    await logger.info("Executing Pass 2 (Sonnet Deep Extraction)...")
    extract_prompt = f"Analyze the following regulatory text and extract compliance gaps according to your system instructions:\n\n<TEXT>\n{text}\n</TEXT>"
    
    content = await invoke_bedrock(model_id=SONNET_MODEL_ID, system=SYSTEM_PROMPT, prompt=extract_prompt, max_tokens=4096)
    
    # Strip potential markdown formatting from LLM output
    if "```json" in content:
        content = content.split("```json")[-1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[-1].split("```")[0].strip()
        
    try:
        gaps = json.loads(content)
        if isinstance(gaps, list):
            return gaps
        elif isinstance(gaps, dict) and "gaps" in gaps:
            return gaps["gaps"]
        return []
    except json.JSONDecodeError as e:
        await logger.error(f"Failed to parse JSON from Sonnet output: {e}. Raw content: {content[:500]}...")
        return []


async def process_scraped_content(content_id: UUID) -> bool:
    """Run the two-pass AI analysis on a piece of scraped content."""
    await logger.info(f"Starting AI analysis for ScrapedContent {content_id}")
    
    async with get_db_session() as session:
        # 1. Fetch the content
        result = await session.execute(
            select(ScrapedContent).where(ScrapedContent.id == content_id)
        )
        content = result.scalar_one_or_none()
        
        if not content:
            await logger.error(f"ScrapedContent {content_id} not found")
            return False
            
        if content.is_processed:
            await logger.warning(f"ScrapedContent {content_id} already processed")
            return True

        try:
            # Pass 1: Filtering (Haiku)
            await logger.info(f"Pass 1: Filtering content with Claude 3 Haiku", {"length": len(content.content_text)})
            is_relevant = await filter_relevant_content(content.content_text)
            
            if not is_relevant:
                await logger.info(f"Content identified as irrelevant, skipping Pass 2")
                content.is_processed = True
                await session.commit()
                return True

            # Pass 2: Extraction (Sonnet)
            await logger.info(f"Pass 2: Extracting gaps with Claude 3.5 Sonnet")
            gaps_data = await extract_compliance_gaps(content.content_text)
            
            if not gaps_data:
                await logger.info(f"No compliance gaps identified in content")
            else:
                await logger.info(f"Identified {len(gaps_data)} potential gaps")
                for gap_dict in gaps_data:
                    new_gap = ComplianceGap(
                        url_id=content.url_id,
                        scraped_content_id=content.id,
                        title=gap_dict.get("title", "Untitled Gap")[:500],
                        description=gap_dict.get("description", ""),
                        requirement=gap_dict.get("requirement", ""),
                        citation=gap_dict.get("citation", ""),
                        severity=GapSeverity(gap_dict.get("severity", "MEDIUM").upper()),
                        status=GapStatus.IDENTIFIED,
                        affected_modules=gap_dict.get("affected_modules", []),
                        is_new_requirement=gap_dict.get("is_new_requirement", False)
                    )
                    session.add(new_gap)
            
            content.is_processed = True
            await session.commit()
            await logger.info(f"AI analysis completed for ScrapedContent {content_id}")
            return True
            
        except Exception as e:
            await logger.error(f"AI analysis failed for ScrapedContent {content_id}: {e}", exc_info=True)
            return False


async def run_analysis(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse SQS records and process them using the LLM logic."""
    for record in event.get("Records", []):
        try:
            body = json.loads(record.get("body", "{}"))
            # Note: Previously it looked for 'regulation_id'. The new Scraper Lambda emits 'scraped_content_id'.
            content_id_str = body.get("scraped_content_id")
            
            if content_id_str:
                content_id = UUID(content_id_str)
                await process_scraped_content(content_id)
            else:
                await logger.error("SQS message missing scraped_content_id.")
        except Exception as e:
            await logger.error(f"Error processing SQS record: {e}", exc_info=True)
            
    return {"statusCode": 200, "body": "Gap analysis complete"}


def handler(event, context):
    """AWS Lambda SQS entry point."""
    return asyncio.get_event_loop().run_until_complete(run_analysis(event))

"""Lambda handler for AI gap analysis using AWS Bedrock."""
import asyncio
import json
import logging
import os
import textwrap
from typing import Dict, Any, List

import boto3
from sqlalchemy import select

from shared.db import get_db_session
from shared.models import ScrapedContent, ComplianceGap, GapSeverity, GapStatus

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Hybrid Bedrock Architecture: Haiku for filtering, Sonnet for deep extraction
HAIKU_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
SONNET_MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"
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

Return ONLY valid JSON.
"""

def chunk_text(text: str, max_chars: int = 10000) -> List[str]:
    """Split text into chunks of max_chars, preferably on paragraph boundaries."""
    return textwrap.wrap(text, width=max_chars, replace_whitespace=False, drop_whitespace=False)


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


async def analyze_chunk(chunk: str) -> List[Dict]:
    """Two-pass AI analysis: Haiku Filter -> Sonnet Extractor."""
    try:
        # Pass 1: Haiku Filter
        logger.info("Executing Pass 1 (Haiku Filtering)...")
        filter_prompt = f"Does the following regulatory text contain any actionable compliance requirements, changes, or mandates that would affect a PACE organization? Respond with ONLY the word YES or NO. Do not explain.\n\n<TEXT>\n{chunk}\n</TEXT>"
        filter_system = "You are a fast legal filter. You only respond with YES or NO."
        
        filter_result = await invoke_bedrock(model_id=HAIKU_MODEL_ID, system=filter_system, prompt=filter_prompt, max_tokens=10)
        
        if "YES" not in filter_result.upper():
            logger.info("Haiku determined no relevant info. Skipping Sonnet.")
            return []
            
        # Pass 2: Sonnet Extraction
        logger.info("Haiku found relevance. Executing Pass 2 (Sonnet Deep Extraction)...")
        extract_prompt = f"Analyze the following regulatory text and extract compliance gaps according to your system instructions:\n\n<TEXT>\n{chunk}\n</TEXT>"
        
        content = await invoke_bedrock(model_id=SONNET_MODEL_ID, system=SYSTEM_PROMPT, prompt=extract_prompt, max_tokens=4096)
        
        # Strip potential markdown formatting from LLM output
        if "```json" in content:
            content = content.split("```json")[-1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[-1].split("```")[0].strip()
            
        gaps = json.loads(content)
        if isinstance(gaps, list):
            return gaps
        elif isinstance(gaps, dict) and "gaps" in gaps:
            return gaps["gaps"]
        return []
        
    except Exception as e:
        logger.error(f"Bedrock invocation failed: {e}")
        return []


async def process_scraped_content(scraped_content_id: str):
    """Fetch scraped text, chunk it, send to AI, and save resulting ComplianceGaps."""
    logger.info(f"Processing scraped content: {scraped_content_id}")
    async with get_db_session() as session:
        result = await session.execute(
            select(ScrapedContent).where(ScrapedContent.id == scraped_content_id)
        )
        scraped_content = result.scalar_one_or_none()
        
        if not scraped_content:
            logger.error(f"ScrapedContent {scraped_content_id} not found in DB.")
            return

        text = scraped_content.content_text
        if not text:
            logger.info("Empty content text, skipping.")
            scraped_content.is_processed = True
            await session.commit()
            return

        chunks = chunk_text(text, max_chars=15000)
        logger.info(f"Split text into {len(chunks)} chunks for Bedrock processing.")
        
        all_gaps = []
        # Process sequentially to avoid aggressive rate limiting initially
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)}")
            gaps = await analyze_chunk(chunk)
            all_gaps.extend(gaps)

        logger.info(f"Bedrock found {len(all_gaps)} total raw gaps. Saving to Database.")
        
        for gap_data in all_gaps:
            try:
                severity_str = gap_data.get("severity", "LOW").upper()
                severity_enum = getattr(GapSeverity, severity_str, GapSeverity.LOW)
                
                gap = ComplianceGap(
                    scraped_content_id=scraped_content.id,
                    title=gap_data.get("title", "Untitled Gap")[:500],
                    description=gap_data.get("description", ""),
                    status=GapStatus.IDENTIFIED,
                    severity=severity_enum,
                    affected_modules=gap_data.get("affected_modules", []),
                    is_new_requirement=gap_data.get("is_new_requirement", False)
                )
                session.add(gap)
            except Exception as e:
                logger.error(f"Failed to save AI-generated gap: {e} | Data: {gap_data}")

        scraped_content.is_processed = True
        await session.commit()
        logger.info(f"Successfully processed {scraped_content_id}.")


async def run_analysis(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse SQS records and process them using the LLM logic."""
    for record in event.get("Records", []):
        try:
            body = json.loads(record.get("body", "{}"))
            # Note: Previously it looked for 'regulation_id'. The new Scraper Lambda emits 'scraped_content_id'.
            content_id = body.get("scraped_content_id") or body.get("regulation_id")
            
            if content_id:
                await process_scraped_content(content_id)
            else:
                logger.warning("SQS record missing scraped_content_id.")
        except Exception as e:
            logger.error(f"Error parsing SQS record: {e}")
            
    return {"statusCode": 200, "body": "Gap analysis complete"}


def handler(event, context):
    """AWS Lambda SQS entry point."""
    return asyncio.get_event_loop().run_until_complete(run_analysis(event))

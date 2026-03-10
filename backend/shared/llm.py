"""Amazon Bedrock LLM client wrapper for compliance analysis."""
import json
import logging

import boto3

from shared.config import get_settings

logger = logging.getLogger(__name__)

_bedrock_client = None


def get_bedrock_client():
    """Get or create the Bedrock runtime client."""
    global _bedrock_client
    if _bedrock_client is None:
        settings = get_settings()
        _bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region,
        )
    return _bedrock_client


async def invoke_llm(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.3,
    response_format: str = "json",
) -> dict | str:
    """Invoke Amazon Bedrock Claude model with structured prompt.

    Args:
        prompt: The user prompt
        system_prompt: System instructions for the model
        max_tokens: Maximum output tokens
        temperature: Temperature for generation (lower = more deterministic)
        response_format: "json" or "text"

    Returns:
        Parsed JSON dict if response_format is "json", otherwise raw text
    """
    settings = get_settings()
    client = get_bedrock_client()

    messages = [{"role": "user", "content": prompt}]

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }

    if system_prompt:
        body["system"] = system_prompt

    try:
        response = client.invoke_model(
            modelId=settings.bedrock_model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )

        response_body = json.loads(response["body"].read())
        content = response_body.get("content", [{}])[0].get("text", "")

        if response_format == "json":
            return _parse_json_response(content)
        return content

    except Exception as e:
        logger.error(f"Bedrock invocation failed: {e}")
        raise


def _parse_json_response(content: str) -> dict:
    """Parse JSON from LLM response, handling markdown code blocks."""
    content = content.strip()

    # Handle markdown code blocks
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]

    try:
        return json.loads(content.strip())
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON from LLM response: {e}")
        logger.debug(f"Raw content: {content[:500]}")
        return {"raw_response": content, "parse_error": str(e)}


# ---- Prompt Templates ----

RELEVANCE_SCORING_SYSTEM = """You are a healthcare regulatory compliance expert specializing in the PACE (Programs of All-Inclusive Care for the Elderly) program.

Your task is to analyze regulatory documents and determine their relevance to a PACE Market Electronic Health Record (EHR) system called PaceCareOnline.

PACE programs serve elderly individuals who qualify for nursing home care but wish to remain in the community. Key areas of PACE compliance include:
- Participant enrollment and eligibility (42 CFR 460.150-460.172)
- Interdisciplinary team (IDT) care planning
- Service delivery requirements and timeframes
- Participant rights, grievances, and appeals
- Quality assessment and performance improvement
- Data reporting to CMS via HPMS
- Personnel medical clearance requirements
- Care coordination and transitions
- Billing, encounter data, and claims processing
- Organizational and contractual requirements

Respond ONLY with valid JSON."""

RELEVANCE_SCORING_PROMPT = """Analyze the following regulatory document and score its relevance to a PACE EHR system.

**Document Title**: {title}
**Source**: {source}
**Document Type**: {document_type}
**Content**:
{content}

Provide your analysis in this JSON format:
{{
    "relevance_score": <float 0.0-1.0>,
    "is_relevant": <boolean>,
    "affected_areas": [<list of affected EHR areas, e.g. "enrollment", "care_planning", "billing">],
    "key_requirements": [<list of specific compliance requirements>],
    "summary": "<2-3 sentence summary of the regulation and its impact>",
    "timeline": {{
        "effective_date": "<date or null>",
        "comment_deadline": "<date or null>",
        "implementation_deadline": "<date or null>"
    }},
    "impact_level": "<critical|high|medium|low>",
    "recommended_actions": [<list of recommended actions for the EHR team>]
}}"""

GAP_ANALYSIS_SYSTEM = """You are a senior software architect and healthcare compliance expert. Your task is to analyze code from a PACE EHR system (PaceCareOnline) and identify compliance gaps relative to new regulatory requirements.

Respond ONLY with valid JSON."""

GAP_ANALYSIS_PROMPT = """Analyze the following code against the regulatory requirement and identify compliance gaps.

**Regulation**: {regulation_title}
**Key Requirements**:
{requirements}

**Code Files**:
{code_content}

Identify gaps in this JSON format:
{{
    "gaps": [
        {{
            "title": "<gap title>",
            "description": "<detailed description of the compliance gap>",
            "severity": "<critical|high|medium|low>",
            "affected_files": [
                {{
                    "file_path": "<path>",
                    "line_range": "<start-end or null>",
                    "issue": "<specific issue in this file>"
                }}
            ],
            "affected_components": [<list of system components affected>],
            "recommended_fix": "<suggested approach to fix>",
            "effort_hours": <estimated hours>,
            "effort_story_points": <estimated story points 1-13>,
            "assigned_team": "<suggested team: backend|frontend|data|devops|qa>"
        }}
    ],
    "overall_assessment": "<summary of compliance posture>",
    "total_effort_hours": <total estimated hours>
}}"""

COMMUNICATION_SYSTEM = """You are a professional healthcare compliance communications writer for Collabrios Health, the company behind PaceCareOnline - a PACE Market EHR system.

Write client-facing communications that are:
- Professional but accessible
- Clear about what has changed and what clients need to know
- Focused on how it affects their PACE operations
- Free of unnecessary jargon

Respond ONLY with valid JSON."""

COMMUNICATION_PROMPT = """Draft a {comm_type} communication for PCO clients about the following regulation:

**Regulation**: {regulation_title}
**Summary**: {regulation_summary}
**Effective Date**: {effective_date}
**Impact Level**: {impact_level}
**Key Requirements**: {key_requirements}
**Current Status**: {current_status}

Provide the communication in this JSON format:
{{
    "subject": "<email subject line>",
    "content_html": "<full HTML email body>",
    "content_plain": "<plain text version>",
    "key_points": [<bullet point summary for quick review>]
}}"""

EXEC_SUMMARY_SYSTEM = """You are a compliance program executive reporting specialist. Create concise, actionable executive summaries for Collabrios Health leadership.

Focus on:
- Key metrics and trends
- Risk areas requiring attention
- Progress against deadlines
- Resource allocation concerns

Respond ONLY with valid JSON."""

EXEC_SUMMARY_PROMPT = """Generate the weekly executive summary for compliance monitoring.

**Report Period**: {week_start} to {week_end}

**Metrics**:
{metrics}

**Active Gaps**:
{gaps_summary}

**Recent Communications**:
{comms_summary}

**Upcoming Deadlines**:
{deadlines}

Provide the summary in this JSON format:
{{
    "summary_html": "<HTML formatted executive summary>",
    "summary_plain": "<plain text version>",
    "metrics": {{
        "new_regulations": <count>,
        "gaps_identified": <count>,
        "gaps_resolved": <count>,
        "communications_sent": <count>,
        "compliance_score": <float 0-100>
    }},
    "risks": [
        {{
            "title": "<risk title>",
            "severity": "<critical|high|medium|low>",
            "description": "<risk description>",
            "mitigation": "<suggested mitigation>"
        }}
    ],
    "highlights": [<key accomplishments this week>],
    "action_items": [<items requiring leadership attention>]
}}"""

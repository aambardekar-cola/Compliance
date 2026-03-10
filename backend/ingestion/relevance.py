"""LLM-based relevance scoring for PACE regulations."""
import logging

from shared.llm import invoke_llm, RELEVANCE_SCORING_SYSTEM, RELEVANCE_SCORING_PROMPT
from ingestion.sources.base import RawRegulation

logger = logging.getLogger(__name__)


async def score_relevance(regulation: RawRegulation) -> dict:
    """Score a regulation's relevance to PACE EHR using Amazon Bedrock.

    Args:
        regulation: Raw regulation document to analyze

    Returns:
        Structured analysis with relevance_score, affected_areas,
        key_requirements, summary, timeline, and recommended_actions
    """
    prompt = RELEVANCE_SCORING_PROMPT.format(
        title=regulation.title,
        source=regulation.source,
        document_type=regulation.document_type,
        content=regulation.content[:8000],  # Truncate for token limits
    )

    try:
        result = await invoke_llm(
            prompt=prompt,
            system_prompt=RELEVANCE_SCORING_SYSTEM,
            max_tokens=2048,
            temperature=0.2,
            response_format="json",
        )

        # Validate expected fields
        if isinstance(result, dict) and "relevance_score" in result:
            # Ensure score is in valid range
            result["relevance_score"] = max(0.0, min(1.0, float(result["relevance_score"])))
            logger.info(
                f"Scored regulation '{regulation.title[:60]}...' "
                f"relevance={result['relevance_score']:.2f}"
            )
            return result
        else:
            logger.warning(f"Unexpected LLM response format: {result}")
            return _default_analysis(regulation)

    except Exception as e:
        logger.error(f"Relevance scoring failed for '{regulation.title[:60]}': {e}")
        return _default_analysis(regulation)


def _default_analysis(regulation: RawRegulation) -> dict:
    """Return a default analysis when LLM scoring fails."""
    return {
        "relevance_score": 0.5,  # Moderate default — requires manual review
        "is_relevant": True,
        "affected_areas": [],
        "key_requirements": [],
        "summary": regulation.summary or regulation.title,
        "timeline": {
            "effective_date": regulation.effective_date.isoformat() if regulation.effective_date else None,
            "comment_deadline": regulation.comment_deadline.isoformat() if regulation.comment_deadline else None,
            "implementation_deadline": None,
        },
        "impact_level": "medium",
        "recommended_actions": ["Manual review required — automated scoring unavailable"],
    }

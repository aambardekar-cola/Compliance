"""Report Generator Lambda handler.

Generates weekly executive compliance reports using Bedrock AI, saves to DB,
and optionally emails via SES.

Trigger: EventBridge cron (weekly) or manual admin API call.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from shared.db import get_db_session
from shared.models import ExecReport
from shared.llm import invoke_llm, EXEC_SUMMARY_SYSTEM, EXEC_SUMMARY_PROMPT
from reporting.scoring import (
    aggregate_week_metrics,
    compute_module_scores,
    build_gaps_summary,
    build_deadlines_summary,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))


async def generate_report(
    week_start: Optional[datetime] = None,
    week_end: Optional[datetime] = None,
    send_email: bool = False,
) -> Dict:
    """Generate a weekly executive report.

    Args:
        week_start: Start of the reporting week (defaults to last Monday).
        week_end: End of the reporting week (defaults to last Sunday).
        send_email: Whether to send the report via SES after generation.

    Returns:
        Serialized report dict with id, metrics, summary, etc.
    """
    # Default to the most recent completed week (Mon-Sun)
    if week_start is None or week_end is None:
        today = datetime.utcnow()
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday + 7)
        week_start = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)

    logger.info(
        "Generating exec report for %s to %s",
        week_start.date().isoformat(),
        week_end.date().isoformat(),
    )

    async with get_db_session() as db:
        # 1. Aggregate metrics from DB
        metrics = await aggregate_week_metrics(db, week_start, week_end)
        module_scores = await compute_module_scores(db)
        metrics["module_scores"] = module_scores

        # 2. Build context for LLM
        gaps_summary = await build_gaps_summary(db)
        deadlines = await build_deadlines_summary(db)
        metrics_text = json.dumps(metrics, indent=2)

        # 3. Call Bedrock for narrative generation
        prompt = EXEC_SUMMARY_PROMPT.format(
            week_start=week_start.date().isoformat(),
            week_end=week_end.date().isoformat(),
            metrics=metrics_text,
            gaps_summary=gaps_summary,
            comms_summary="N/A",
            deadlines=deadlines,
        )

        try:
            llm_response = await invoke_llm(
                prompt=prompt,
                system_prompt=EXEC_SUMMARY_SYSTEM,
                max_tokens=4096,
                temperature=0.3,
                response_format="json",
            )
        except Exception:
            logger.exception("Bedrock invocation failed; generating fallback report")
            llm_response = _fallback_report(metrics, week_start, week_end)

        # 4. Save to DB
        report = ExecReport(
            week_start=week_start.date(),
            week_end=week_end.date(),
            summary_html=llm_response.get("summary_html", "<p>Report generation pending.</p>"),
            summary_plain=llm_response.get("summary_plain", "Report generation pending."),
            metrics=metrics,
            risks=llm_response.get("risks", []),
            highlights=llm_response.get("highlights", []),
        )
        db.add(report)
        await db.flush()
        report_id = str(report.id)

        logger.info("Saved exec report %s", report_id)

        # 5. Optional email delivery
        if send_email:
            recipients = _get_recipients()
            if recipients:
                await _send_report_email(report, recipients)
                report.sent_to = recipients
                report.sent_at = datetime.utcnow()

    return {
        "id": report_id,
        "week_start": week_start.date().isoformat(),
        "week_end": week_end.date().isoformat(),
        "metrics": metrics,
        "risks": llm_response.get("risks", []),
        "highlights": llm_response.get("highlights", []),
        "status": "generated",
    }


def _fallback_report(metrics: Dict, week_start: datetime, week_end: datetime) -> Dict:
    """Generate a simple fallback report when Bedrock is unavailable."""
    score = metrics.get("compliance_score", 0)
    return {
        "summary_html": (
            f"<h2>Weekly Compliance Report</h2>"
            f"<p>Period: {week_start.date().isoformat()} to {week_end.date().isoformat()}</p>"
            f"<ul>"
            f"<li><strong>New Regulations:</strong> {metrics.get('new_regulations', 0)}</li>"
            f"<li><strong>Gaps Identified:</strong> {metrics.get('gaps_identified', 0)}</li>"
            f"<li><strong>Gaps Resolved:</strong> {metrics.get('gaps_resolved', 0)}</li>"
            f"<li><strong>Compliance Score:</strong> {score}%</li>"
            f"</ul>"
        ),
        "summary_plain": (
            f"Weekly Compliance Report ({week_start.date()} to {week_end.date()})\n"
            f"New Regulations: {metrics.get('new_regulations', 0)}\n"
            f"Gaps Identified: {metrics.get('gaps_identified', 0)}\n"
            f"Gaps Resolved: {metrics.get('gaps_resolved', 0)}\n"
            f"Compliance Score: {score}%"
        ),
        "risks": [],
        "highlights": [],
    }


def _get_recipients() -> List[str]:
    """Get report recipients from environment or config."""
    env_recipients = os.environ.get("REPORT_RECIPIENTS", "")
    if env_recipients:
        return [r.strip() for r in env_recipients.split(",") if r.strip()]
    return []


async def _send_report_email(report: ExecReport, recipients: List[str]) -> None:
    """Send the report via SES."""
    try:
        import boto3
        ses = boto3.client("ses", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        from_email = os.environ.get("SES_FROM_EMAIL", "compliance@collabrios.com")

        ses.send_email(
            Source=from_email,
            Destination={"ToAddresses": recipients},
            Message={
                "Subject": {
                    "Data": f"PCO Compliance Report — Week of {report.week_start.isoformat()}",
                },
                "Body": {
                    "Html": {"Data": report.summary_html},
                    "Text": {"Data": report.summary_plain or ""},
                },
            },
        )
        logger.info("Sent report email to %d recipients", len(recipients))
    except Exception:
        logger.exception("Failed to send report email")


def handler(event, context):
    """AWS Lambda entry point."""
    logger.info("Report generation Lambda invoked: %s", json.dumps(event))

    send_email = event.get("send_email", True)

    result = asyncio.get_event_loop().run_until_complete(
        generate_report(send_email=send_email)
    )

    logger.info("Report generation complete: %s", result.get("id"))
    return {
        "statusCode": 200,
        "body": json.dumps(result),
    }

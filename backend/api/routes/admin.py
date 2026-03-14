from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
import os
import re
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session_dependency
from shared.models import (
    ComplianceRuleUrl, ScrapedContent, ComplianceGap, Regulation,
    PipelineLog, UserRole, SystemConfig,
)
from shared import statsig_client
from api.middleware.auth import require_role
import importlib
import traceback
from shared.logging import get_pipeline_logger

logger = get_pipeline_logger("admin")

router = APIRouter()

# ---- Schemas ----

class ComplianceUrlBase(BaseModel):
    name: str
    url: str
    description: Optional[str] = None
    is_active: bool = True

class ComplianceUrlCreate(ComplianceUrlBase):
    pass


class GenerateReportRequest(BaseModel):
    """Optional custom date range for report generation."""
    week_start: Optional[str] = None  # ISO date string
    week_end: Optional[str] = None    # ISO date string


class RecipientsUpdate(BaseModel):
    """Payload for updating report recipients."""
    emails: List[str]

    @field_validator("emails", mode="before")
    @classmethod
    def validate_emails(cls, v):  # noqa: N805
        max_recipients = statsig_client.get_config(
            "reporting", "max_recipients", 20,
        )
        if len(v) > max_recipients:
            raise ValueError(f"Maximum {max_recipients} recipients allowed")
        pattern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        for email in v:
            if not pattern.match(email.strip()):
                raise ValueError(f"Invalid email: {email}")
        return [e.strip() for e in v]

class ComplianceUrlUpdate(ComplianceUrlBase):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class ComplianceUrlResponse(ComplianceUrlBase):
    id: UUID

    class Config:
        from_attributes = True

class PipelineLogResponse(BaseModel):
    id: UUID
    component: str
    level: str
    message: str
    details: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True

# ---- Routes ----

@router.get("/urls", response_model=List[ComplianceUrlResponse], dependencies=[Depends(require_role([UserRole.INTERNAL_ADMIN]))])
async def list_urls(session: AsyncSession = Depends(get_session_dependency)):
    """List all configured compliance rule URLs."""
    result = await session.execute(
        select(ComplianceRuleUrl).order_by(ComplianceRuleUrl.created_at.desc())
    )
    return result.scalars().all()

@router.post("/urls", response_model=ComplianceUrlResponse, dependencies=[Depends(require_role([UserRole.INTERNAL_ADMIN]))])
async def create_url(url_data: ComplianceUrlCreate, session: AsyncSession = Depends(get_session_dependency)):
    """Create a new compliance rule URL to monitor."""
    new_url = ComplianceRuleUrl(**url_data.model_dump())
    session.add(new_url)
    await session.commit()
    await session.refresh(new_url)
    return new_url

@router.put("/urls/{url_id}", response_model=ComplianceUrlResponse, dependencies=[Depends(require_role([UserRole.INTERNAL_ADMIN]))])
async def update_url(url_id: UUID, url_data: ComplianceUrlUpdate, session: AsyncSession = Depends(get_session_dependency)):
    """Update an existing compliance rule URL configuration."""
    result = await session.execute(
        select(ComplianceRuleUrl).where(ComplianceRuleUrl.id == url_id)
    )
    url_obj = result.scalar_one_or_none()
    
    if not url_obj:
        raise HTTPException(status_code=404, detail="URL not found")
    
    for key, value in url_data.model_dump(exclude_unset=True).items():
        setattr(url_obj, key, value)
        
    await session.commit()
    await session.refresh(url_obj)
    return url_obj

@router.delete("/urls/{url_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_role([UserRole.INTERNAL_ADMIN]))])
async def delete_url(url_id: UUID, session: AsyncSession = Depends(get_session_dependency)):
    """Delete a compliance rule URL."""
    result = await session.execute(
        select(ComplianceRuleUrl).where(ComplianceRuleUrl.id == url_id)
    )
    url_obj = result.scalar_one_or_none()
    
    if not url_obj:
        raise HTTPException(status_code=404, detail="URL not found")
        
    await session.delete(url_obj)
    await session.commit()
    return None

@router.get("/diagnostics", dependencies=[Depends(require_role([UserRole.INTERNAL_ADMIN]))])
async def get_diagnostics(session: AsyncSession = Depends(get_session_dependency)):
    """Get internal pipeline status and recent activity."""
    scraped_count_result = await session.execute(select(func.count()).select_from(ScrapedContent))
    gap_count_result = await session.execute(select(func.count()).select_from(ComplianceGap))
    log_count_result = await session.execute(select(func.count()).select_from(PipelineLog))
    reg_count_result = await session.execute(select(func.count()).select_from(Regulation))
    
    scraped_count = scraped_count_result.scalar()
    gap_count = gap_count_result.scalar()
    log_count = log_count_result.scalar()
    reg_count = reg_count_result.scalar()
    
    latest_scrapes = await session.execute(
        select(ScrapedContent).order_by(ScrapedContent.scraped_at.desc()).limit(5)
    )
    
    latest_gaps = await session.execute(
        select(ComplianceGap).order_by(ComplianceGap.created_at.desc()).limit(5)
    )
    
    return {
        "counts": {
            "scraped_content": scraped_count,
            "regulations": reg_count,
            "compliance_gaps": gap_count,
            "pipeline_logs": log_count
        },
        "latest_scrapes": [
            {"id": str(s.id), "url_id": str(s.url_id), "scraped_at": s.scraped_at.isoformat(), "is_processed": s.is_processed}
            for s in latest_scrapes.scalars().all()
        ],
        "latest_gaps": [
            {"id": str(g.id), "title": g.title, "severity": g.severity.value, "created_at": g.created_at.isoformat()}
            for g in latest_gaps.scalars().all()
        ]
    }

@router.get("/logs", response_model=List[PipelineLogResponse], dependencies=[Depends(require_role([UserRole.INTERNAL_ADMIN]))])
async def list_pipeline_logs(
    component: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session_dependency)
):
    """List internal pipeline logs with filtering."""
    query = select(PipelineLog).order_by(PipelineLog.timestamp.desc()).limit(limit)
    
    if component:
        query = query.where(PipelineLog.component == component)
    if level:
        query = query.where(PipelineLog.level == level)
        
    result = await session.execute(query)
    return result.scalars().all()

@router.post("/trigger-scraper", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_role([UserRole.INTERNAL_ADMIN]))])
async def trigger_scraper_manually():
    """Manually trigger the scraper Lambda."""
    import boto3
    import os
    
    deploy_env = os.environ.get("APP_ENV", "dev")
    lambda_client = boto3.client("lambda", region_name="us-east-2")
    
    try:
        functions = lambda_client.list_functions()
        scraper_name = None
        for f in functions.get("Functions", []):
            name = f["FunctionName"]
            if "ScraperHandler" in name and deploy_env in name:
                scraper_name = name
                break
        
        if not scraper_name:
            await logger.error("Scraper Lambda function not found")
            raise HTTPException(status_code=404, detail="Scraper Lambda not found")
            
        lambda_client.invoke(
            FunctionName=scraper_name,
            InvocationType="Event"
        )
        await logger.info(f"Manually triggered scraper: {scraper_name}")
        return {"status": "triggered", "function": scraper_name}
    except Exception as e:
        await logger.error(f"Failed to trigger scraper: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/verify-modules", dependencies=[Depends(require_role([UserRole.INTERNAL_ADMIN]))])
async def verify_modules():
    """Check if backend modules are importable (for debugging Lambda environment)."""
    results = {}
    modules_to_check = [
        "shared.db",
        "shared.models",
        "shared.logging",
        "lambdas.scraper.main",
        "analysis.handler"
    ]
    
    for mod_name in modules_to_check:
        try:
            importlib.import_module(mod_name)
            results[mod_name] = "OK"
        except Exception:
            results[mod_name] = traceback.format_exc()
            
    return results

@router.post("/trigger-analysis", dependencies=[Depends(require_role([UserRole.INTERNAL_ADMIN]))])
async def trigger_analysis(session: AsyncSession = Depends(get_session_dependency)):
    """Re-queue all unprocessed ScrapedContent items for Bedrock analysis."""
    import boto3
    result = await session.execute(
        select(ScrapedContent).where(ScrapedContent.is_processed == False)
    )
    unprocessed = result.scalars().all()
    
    if not unprocessed:
        return {"status": "no_unprocessed_content", "count": 0}
    
    queue_url = os.environ.get("ANALYSIS_QUEUE_URL")
    if not queue_url:
        raise HTTPException(status_code=500, detail="ANALYSIS_QUEUE_URL not configured")
    
    import json
    sqs = boto3.client("sqs")
    queued = 0
    for content in unprocessed:
        try:
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps({
                    "scraped_content_id": str(content.id),
                    "url_name": f"re-analysis-{content.url_id}"
                })
            )
            queued += 1
        except Exception as e:
            await logger.error(f"Failed to queue content {content.id}: {e}")
    
    await logger.info(f"Manually triggered analysis for {queued} unprocessed items")
    return {"status": "triggered", "queued": queued, "total_unprocessed": len(unprocessed)}

@router.post("/reset-data", dependencies=[Depends(require_role([UserRole.INTERNAL_ADMIN]))])
async def reset_data_and_rescrape(session: AsyncSession = Depends(get_session_dependency)):
    """Wipe all derived data (gaps, regulations, scraped content) and re-trigger the scraper.

    Keeps compliance_rule_urls intact so the scraper picks up all configured URLs.
    """
    import boto3
    from sqlalchemy import text

    await logger.info("Admin reset-data initiated — truncating derived tables")

    # Truncate in dependency order (CASCADE handles FK refs)
    for table in ["compliance_gaps", "regulations", "scraped_content",
                   "pipeline_logs", "pipeline_runs", "admin_notifications"]:
        await session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
    await session.commit()
    await logger.info("All derived tables truncated successfully")

    # Re-trigger scraper
    deploy_env = os.environ.get("APP_ENV", "dev")
    lambda_client = boto3.client("lambda", region_name="us-east-2")
    scraper_triggered = False
    scraper_name = None

    try:
        functions = lambda_client.list_functions()
        for f in functions.get("Functions", []):
            name = f["FunctionName"]
            if "ScraperHandler" in name and deploy_env in name:
                scraper_name = name
                break

        if scraper_name:
            lambda_client.invoke(FunctionName=scraper_name, InvocationType="Event")
            scraper_triggered = True
            await logger.info(f"Scraper triggered after reset: {scraper_name}")
    except Exception as e:
        await logger.error(f"Failed to trigger scraper after reset: {e}")

    return {
        "status": "reset_complete",
        "tables_truncated": ["compliance_gaps", "regulations", "scraped_content",
                             "pipeline_logs", "pipeline_runs", "admin_notifications"],
        "scraper_triggered": scraper_triggered,
        "scraper_function": scraper_name,
    }


# ---- Report Generation ----

@router.post("/reports/generate")
async def generate_report(
    request=Depends(require_role(UserRole.INTERNAL_ADMIN)),
    db: AsyncSession = Depends(get_session_dependency),
    body: GenerateReportRequest = None,
):
    """Manually trigger executive report generation with optional date range."""
    from reporting.handler import generate_report as run_generate

    kwargs: Dict[str, Any] = {"send_email": False}

    if body and body.week_start and body.week_end:
        try:
            kwargs["week_start"] = datetime.fromisoformat(body.week_start)
            kwargs["week_end"] = datetime.fromisoformat(body.week_end)
        except ValueError:
            raise HTTPException(400, "Invalid date format. Use ISO 8601 (YYYY-MM-DD)")

    try:
        result = await run_generate(**kwargs)
        return {"status": "ok", "report": result}
    except Exception as e:
        raise HTTPException(500, f"Report generation failed: {e}")


@router.post("/reports/{report_id}/send")
async def send_report(
    report_id: UUID,
    request=Depends(require_role(UserRole.INTERNAL_ADMIN)),
    db: AsyncSession = Depends(get_session_dependency),
):
    """Send an existing report via SES email."""
    from shared.models import ExecReport
    from reporting.handler import _send_report_email, get_recipients

    result = await db.execute(
        select(ExecReport).where(ExecReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(404, "Report not found")

    recipients = await get_recipients(db)
    if not recipients:
        raise HTTPException(
            400,
            "No recipients configured. Add recipients via Admin > Email Settings.",
        )

    await _send_report_email(report, recipients)
    report.sent_to = recipients
    report.sent_at = datetime.utcnow()
    await db.commit()

    return {"status": "sent", "recipients": recipients}


# ---- Report Recipients ----

RECIPIENTS_CONFIG_KEY = "report_recipients"


@router.get("/reports/recipients")
async def get_report_recipients(
    request=Depends(require_role(UserRole.INTERNAL_ADMIN)),
    db: AsyncSession = Depends(get_session_dependency),
):
    """Get configured report email recipients."""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == RECIPIENTS_CONFIG_KEY)
    )
    config = result.scalar_one_or_none()

    if config and config.value:
        return {"emails": config.value}

    # Fallback to env var (with Statsig defaults)
    default = statsig_client.get_config("reporting", "default_recipients", "")
    env_val = os.environ.get("REPORT_RECIPIENTS", default)
    emails = [e.strip() for e in env_val.split(",") if e.strip()] if env_val else []
    return {"emails": emails}


@router.put("/reports/recipients")
async def update_report_recipients(
    body: RecipientsUpdate,
    request=Depends(require_role(UserRole.INTERNAL_ADMIN)),
    db: AsyncSession = Depends(get_session_dependency),
):
    """Update report email recipients (stored in SystemConfig)."""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == RECIPIENTS_CONFIG_KEY)
    )
    config = result.scalar_one_or_none()

    if config:
        config.value = body.emails
    else:
        config = SystemConfig(
            key=RECIPIENTS_CONFIG_KEY,
            value=body.emails,
            description="Email recipients for executive compliance reports",
        )
        db.add(config)

    await db.commit()
    return {"emails": body.emails, "count": len(body.emails)}



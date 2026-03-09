from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
import os
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session_dependency
from shared.models import ComplianceRuleUrl, ScrapedContent, ComplianceGap, PipelineLog, UserRole
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
    
    scraped_count = scraped_count_result.scalar()
    gap_count = gap_count_result.scalar()
    log_count = log_count_result.scalar()
    
    latest_scrapes = await session.execute(
        select(ScrapedContent).order_by(ScrapedContent.scraped_at.desc()).limit(5)
    )
    
    latest_gaps = await session.execute(
        select(ComplianceGap).order_by(ComplianceGap.created_at.desc()).limit(5)
    )
    
    return {
        "counts": {
            "scraped_content": scraped_count,
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

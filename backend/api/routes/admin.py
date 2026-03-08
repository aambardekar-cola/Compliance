from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session_dependency
from shared.models import ComplianceRuleUrl, UserRole
from api.middleware.auth import require_role

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

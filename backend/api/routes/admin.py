from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from shared.db import get_session
from shared.models import ComplianceRuleUrl, UserRole
from api.middleware.auth import require_role

router = APIRouter()

# ---- Schemas ----

class ComplianceUrlBase(BaseModel):
    name: str
    url: str
    description: str | None = None
    is_active: bool = True

class ComplianceUrlCreate(ComplianceUrlBase):
    pass

class ComplianceUrlUpdate(ComplianceUrlBase):
    pass

class ComplianceUrlResponse(ComplianceUrlBase):
    id: UUID

    class Config:
        from_attributes = True


# ---- Routes ----

@router.get("/urls", response_model=List[ComplianceUrlResponse], dependencies=[Depends(require_role(UserRole.INTERNAL_ADMIN))])
async def list_urls(session: Session = Depends(get_session)):
    """List all configured compliance rule URLs."""
    urls = session.query(ComplianceRuleUrl).order_by(ComplianceRuleUrl.created_at.desc()).all()
    return urls

@router.post("/urls", response_model=ComplianceUrlResponse, dependencies=[Depends(require_role(UserRole.INTERNAL_ADMIN))])
async def create_url(url_data: ComplianceUrlCreate, session: Session = Depends(get_session)):
    """Create a new compliance rule URL to monitor."""
    new_url = ComplianceRuleUrl(**url_data.model_dump())
    session.add(new_url)
    session.commit()
    session.refresh(new_url)
    return new_url

@router.put("/urls/{url_id}", response_model=ComplianceUrlResponse, dependencies=[Depends(require_role(UserRole.INTERNAL_ADMIN))])
async def update_url(url_id: UUID, url_data: ComplianceUrlUpdate, session: Session = Depends(get_session)):
    """Update an existing compliance rule URL configuration."""
    url_obj = session.query(ComplianceRuleUrl).filter(ComplianceRuleUrl.id == url_id).first()
    if not url_obj:
        raise HTTPException(status_code=404, detail="URL not found")
        
    for key, value in url_data.model_dump().items():
        setattr(url_obj, key, value)
        
    session.commit()
    session.refresh(url_obj)
    return url_obj

@router.delete("/urls/{url_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_role(UserRole.INTERNAL_ADMIN))])
async def delete_url(url_id: UUID, session: Session = Depends(get_session)):
    """Delete a compliance rule URL."""
    url_obj = session.query(ComplianceRuleUrl).filter(ComplianceRuleUrl.id == url_id).first()
    if not url_obj:
        raise HTTPException(status_code=404, detail="URL not found")
        
    session.delete(url_obj)
    session.commit()
    return None

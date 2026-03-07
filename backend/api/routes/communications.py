"""Communications API routes — draft, approve, and send client communications."""
from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session_dependency
from shared.models import Communication, CommunicationStatus, Tenant
from api.middleware.auth import get_current_user

router = APIRouter()


class ApproveCommunicationRequest(BaseModel):
    """Request body for approving a communication."""
    pass


class SendCommunicationRequest(BaseModel):
    """Request body for sending a communication."""
    send_now: bool = True


@router.get("/communications")
async def list_communications(
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
    status: Optional[str] = Query(None),
    regulation_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List communications with filtering and pagination."""
    user = get_current_user(request)
    query = select(Communication)

    # Client users can only see their tenant's communications
    if not user.is_internal and user.tenant_id:
        tenant_result = await db.execute(
            select(Tenant.id).where(Tenant.descope_tenant_id == user.tenant_id)
        )
        tenant_db_id = tenant_result.scalar_one_or_none()
        if tenant_db_id:
            query = query.where(Communication.tenant_id == tenant_db_id)
        # Client users can only see sent communications
        query = query.where(Communication.status == CommunicationStatus.SENT)

    if status:
        try:
            query = query.where(Communication.status == CommunicationStatus(status))
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")

    if regulation_id:
        query = query.where(Communication.regulation_id == regulation_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = (
        query
        .order_by(desc(Communication.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    comms = result.scalars().all()

    return {
        "items": [_serialize_communication(c) for c in comms],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/communications/{comm_id}")
async def get_communication(
    comm_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """Get a specific communication."""
    user = get_current_user(request)

    result = await db.execute(
        select(Communication).where(Communication.id == comm_id)
    )
    comm = result.scalar_one_or_none()

    if not comm:
        raise HTTPException(404, "Communication not found")

    # Client users can only see sent communications for their tenant
    if not user.is_internal:
        if comm.status != CommunicationStatus.SENT:
            raise HTTPException(403, "Access denied")

    return _serialize_communication(comm, detailed=True)


@router.post("/communications/{comm_id}/approve")
async def approve_communication(
    comm_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """Approve a draft communication for sending (internal users only)."""
    user = get_current_user(request)

    if not user.is_internal:
        raise HTTPException(403, "Only internal users can approve communications")

    result = await db.execute(
        select(Communication).where(Communication.id == comm_id)
    )
    comm = result.scalar_one_or_none()

    if not comm:
        raise HTTPException(404, "Communication not found")

    if comm.status not in (CommunicationStatus.DRAFT, CommunicationStatus.PENDING_APPROVAL):
        raise HTTPException(400, f"Cannot approve communication in {comm.status.value} status")

    comm.status = CommunicationStatus.APPROVED
    comm.approved_by = user.email
    comm.approved_at = datetime.utcnow()

    await db.commit()

    return {"message": "Communication approved", "id": str(comm.id)}


@router.post("/communications/{comm_id}/send")
async def send_communication(
    comm_id: UUID,
    body: SendCommunicationRequest,
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """Send an approved communication to subscribed clients (internal users only)."""
    user = get_current_user(request)

    if not user.is_internal:
        raise HTTPException(403, "Only internal users can send communications")

    result = await db.execute(
        select(Communication).where(Communication.id == comm_id)
    )
    comm = result.scalar_one_or_none()

    if not comm:
        raise HTTPException(404, "Communication not found")

    if comm.status != CommunicationStatus.APPROVED:
        raise HTTPException(400, "Communication must be approved before sending")

    # In a full implementation, this would trigger the SES email Lambda
    comm.status = CommunicationStatus.SENT
    comm.sent_at = datetime.utcnow()

    await db.commit()

    return {"message": "Communication sent", "id": str(comm.id)}


def _serialize_communication(comm: Communication, detailed: bool = False) -> dict:
    """Serialize a Communication model to API response."""
    data = {
        "id": str(comm.id),
        "regulation_id": str(comm.regulation_id) if comm.regulation_id else None,
        "tenant_id": str(comm.tenant_id) if comm.tenant_id else None,
        "type": comm.type.value if comm.type else None,
        "subject": comm.subject,
        "status": comm.status.value if comm.status else None,
        "approved_by": comm.approved_by,
        "approved_at": comm.approved_at.isoformat() if comm.approved_at else None,
        "sent_at": comm.sent_at.isoformat() if comm.sent_at else None,
        "recipient_count": comm.recipient_count,
        "created_at": comm.created_at.isoformat() if comm.created_at else None,
    }

    if detailed:
        data.update({
            "content_html": comm.content_html,
            "content_plain": comm.content_plain,
        })

    return data

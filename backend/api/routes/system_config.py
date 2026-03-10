"""System Config API routes — admin key-value settings management."""
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session_dependency
from shared.models import SystemConfig

router = APIRouter()


class SystemConfigUpdate(BaseModel):
    """Request body for upserting a system config entry."""
    value: Any
    description: Optional[str] = None


@router.get("/system-config")
async def list_system_configs(
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """List all system configuration entries."""
    result = await db.execute(
        select(SystemConfig).order_by(SystemConfig.key)
    )
    configs = result.scalars().all()

    return {
        "items": [_serialize_config(c) for c in configs],
        "total": len(configs),
    }


@router.get("/system-config/{key}")
async def get_system_config(
    key: str,
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """Get a single system config value by key."""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(404, f"Config key '{key}' not found")

    return _serialize_config(config)


@router.put("/system-config/{key}")
async def upsert_system_config(
    key: str,
    body: SystemConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_session_dependency),
):
    """Create or update a system config entry."""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    config = result.scalar_one_or_none()

    if config:
        config.value = body.value
        if body.description is not None:
            config.description = body.description
    else:
        config = SystemConfig(
            key=key,
            value=body.value,
            description=body.description,
        )
        db.add(config)

    await db.commit()
    await db.refresh(config)

    return _serialize_config(config)


def _serialize_config(config: SystemConfig) -> dict:
    """Serialize a SystemConfig model to API response."""
    return {
        "id": str(config.id),
        "key": config.key,
        "value": config.value,
        "description": config.description,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }

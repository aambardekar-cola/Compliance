"""Database access layer using SQLAlchemy async with Aurora PostgreSQL."""
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import boto3
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from shared.config import get_settings
from shared.models import Base

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None


import asyncio

def _build_database_url() -> str:
    """Build the database URL from config or AWS Secrets Manager."""
    settings = get_settings()

    if settings.is_production and settings.db_secret_arn:
        import boto3
        # In production, fetch credentials from Secrets Manager (non-blocking)
        # Note: Depending on event loop state, a synchronous call here
        # is dangerous. We will return the database URL directly but we should
        # use asyncio.to_thread in get_engine calling this instead.
        pass
    return settings.database_url


async def _get_secret_database_url(settings) -> str:
    """Async wrapper to fetch DB credentials from Secrets Manager."""
    def fetch_secret():
        import boto3
        client = boto3.client("secretsmanager", region_name=settings.aws_region)
        response = client.get_secret_value(SecretId=settings.db_secret_arn)
        return json.loads(response["SecretString"])
    
    secret = await asyncio.to_thread(fetch_secret)
    username = secret["username"]
    password = secret["password"]
    host = settings.db_proxy_endpoint
    database = "compliance_db"
    return f"postgresql+asyncpg://{username}:{password}@{host}:5432/{database}"


async def get_engine():
    """Get or create the async SQLAlchemy engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        if settings.is_production and settings.db_secret_arn:
            database_url = await _get_secret_database_url(settings)
        else:
            database_url = settings.database_url
            
        _engine = create_async_engine(
            database_url,
            echo=get_settings().log_level == "DEBUG",
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,  # Recycle connections every 5 minutes
        )
    return _engine


def get_session_factory():
    """Get or create the async session factory."""
    global _session_factory
    if _session_factory is None:
        engine = await get_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session.

    Usage:
        async with get_db_session() as session:
            result = await session.execute(select(Regulation))
    """
    factory = await get_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_session_dependency() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with get_db_session() as session:
        yield session


async def init_db():
    """Initialize the database schema (for development/testing)."""
    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema initialized")


async def close_db():
    """Close the database engine connections."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
    logger.info("Database connections closed")

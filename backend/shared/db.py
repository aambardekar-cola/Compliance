"""Database access layer using SQLAlchemy async with Aurora PostgreSQL."""
import json
import logging
from contextlib import asynccontextmanager
import asyncio
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from shared.config import get_settings
from shared.models import Base

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None




def _build_database_url() -> str:
    """Build the database URL from config or AWS Secrets Manager."""
    settings = get_settings()

    if settings.is_production and settings.db_secret_arn:
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
            
        connect_args = {}
        if "postgresql" in database_url:
            connect_args = {
                "prepared_statement_cache_size": 0,
                "statement_cache_size": 0
            }
            
        _engine = create_async_engine(
            database_url,
            echo=get_settings().log_level == "DEBUG",
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,  # Recycle connections every 5 minutes
            connect_args=connect_args
        )
    return _engine


async def get_session_factory():
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
        
        # Incremental schema migrations — ALTER TABLE won't be run by create_all
        # on existing tables, so we add new columns explicitly (idempotent).
        # These are PostgreSQL-specific (DO $$ blocks, IF NOT EXISTS on ALTER TABLE).
        # SQLite uses create_all above which handles the full schema.
        dialect_name = engine.dialect.name
        if dialect_name == "postgresql":
            migrations = [
                # Phase 1.5: Incremental chunking
                "ALTER TABLE scraped_content ADD COLUMN IF NOT EXISTS chunks_processed INTEGER DEFAULT 0",
                "ALTER TABLE scraped_content ADD COLUMN IF NOT EXISTS total_chunks INTEGER",
                # Phase 2: Regulation→Gap linking + module mapping
                "DO $$ BEGIN CREATE TYPE affectedlayer AS ENUM ('frontend','backend','both','unknown'); EXCEPTION WHEN duplicate_object THEN NULL; END $$",
                "ALTER TABLE compliance_gaps ADD COLUMN IF NOT EXISTS regulation_id UUID REFERENCES regulations(id) ON DELETE SET NULL",
                "ALTER TABLE compliance_gaps ADD COLUMN IF NOT EXISTS affected_layer affectedlayer DEFAULT 'unknown'",
                "ALTER TABLE regulations ADD COLUMN IF NOT EXISTS scraped_content_id UUID REFERENCES scraped_content(id) ON DELETE SET NULL",
                "ALTER TABLE regulations ADD COLUMN IF NOT EXISTS document_chunk_hash VARCHAR(64)",
                # Phase 2.5: Pipeline observability & notifications
                "DO $$ BEGIN CREATE TYPE pipelineruntype AS ENUM ('scraper','ingestion','analysis'); EXCEPTION WHEN duplicate_object THEN NULL; END $$",
                "DO $$ BEGIN CREATE TYPE pipelinerunstatus AS ENUM ('started','completed','failed','partial'); EXCEPTION WHEN duplicate_object THEN NULL; END $$",
                "DO $$ BEGIN CREATE TYPE notificationtype AS ENUM ('pipeline_completed','pipeline_failed','new_regulations','new_gaps','error','info'); EXCEPTION WHEN duplicate_object THEN NULL; END $$",
                # Phase 2.7: Regulation lifecycle & configurable gap analysis
                "DO $$ BEGIN ALTER TYPE regulationstatus ADD VALUE IF NOT EXISTS 'unknown'; EXCEPTION WHEN duplicate_object THEN NULL; END $$",
                "ALTER TABLE regulations ADD COLUMN IF NOT EXISTS program_area JSONB DEFAULT '[]'::jsonb",
                "ALTER TABLE regulations ADD COLUMN IF NOT EXISTS gap_analysis_requested BOOLEAN DEFAULT FALSE",
                # Phase 2.7: system_configs — fix stale index + ensure id has server default
                "DROP INDEX IF EXISTS ix_system_configs_key",
                "ALTER TABLE system_configs ALTER COLUMN id SET DEFAULT gen_random_uuid()",
                # Seed default gap_analysis_statuses config (idempotent)
                """INSERT INTO system_configs (key, value, description)
                VALUES ('gap_analysis_statuses', '["final_rule", "effective"]'::jsonb,
                        'Regulation statuses that automatically trigger gap analysis')
                ON CONFLICT (key) DO NOTHING""",
            ]
            for sql in migrations:
                await conn.execute(text(sql))
            
    logger.info("Database schema initialized")


async def close_db():
    """Close the database engine connections."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
    logger.info("Database connections closed")

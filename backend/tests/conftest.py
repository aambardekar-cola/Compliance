"""Shared test fixtures for the compliance API tests.

Provides:
- Async SQLite test database (in-memory)
- Mock auth middleware (bypasses Descope, injects mock users)
- HTTPX async test client
- Seed data factories
"""
import asyncio
import uuid
from datetime import datetime, date, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from shared.models import (
    Base, Regulation, ComplianceGap, ComplianceRuleUrl, ScrapedContent,
    Tenant, PipelineRun, AdminNotification,
    RegulationStatus, GapSeverity, GapStatus, AffectedLayer,
    PipelineRunType, PipelineRunStatus,
    NotificationType, ExecReport,
)
from shared.auth import CurrentUser

# ---------------------------------------------------------------------------
# Event-loop fixture (session-scoped)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop():
    """Use a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# SQLite async engine (session-scoped, shared across all tests)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create an async SQLite engine for testing."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///",
        echo=False,
    )

    # SQLite needs special handling for nested transactions
    @event.listens_for(eng.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield eng
    await eng.dispose()


# ---------------------------------------------------------------------------
# DB session (per-test, with rollback)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def db_session(engine):
    """Provide a transactional DB session that cleans up tables between tests."""
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Clean all tables before each test (reverse dependency order)
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()
        yield session


# ---------------------------------------------------------------------------
# Mock users
# ---------------------------------------------------------------------------
ADMIN_USER = CurrentUser(
    user_id="test-admin-123", email="admin@collabrios.com", name="Test Admin",
    tenant_id=None, tenant_name=None, roles=["internal_admin"], permissions=[]
)

INTERNAL_USER = CurrentUser(
    user_id="test-internal-456", email="dev@collabrios.com", name="Test Dev",
    tenant_id=None, tenant_name=None, roles=["internal_user"], permissions=[]
)

CLIENT_ADMIN = CurrentUser(
    user_id="test-client-789", email="admin@sunrisepace.org", name="Test Client Admin",
    tenant_id="tenant-001", tenant_name="Sunrise PACE", roles=["client_admin"], permissions=[]
)

CLIENT_USER = CurrentUser(
    user_id="test-client-abc", email="user@sunrisepace.org", name="Test Client User",
    tenant_id="tenant-001", tenant_name="Sunrise PACE", roles=["client_user"], permissions=[]
)

# Map of test tokens to mock users
MOCK_TOKENS = {
    "test-admin-token": ADMIN_USER,
    "test-internal-token": INTERNAL_USER,
    "test-client-admin-token": CLIENT_ADMIN,
    "test-client-user-token": CLIENT_USER,
}


# ---------------------------------------------------------------------------
# Test app + client (override auth + DB)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def app(db_session):
    """Create a test FastAPI app with mocked auth and DB session."""
    import os
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///")
    os.environ.setdefault("APP_ENV", "test")
    os.environ.setdefault("DESCOPE_PROJECT_ID", "test-project")
    os.environ["MOCK_AUTH_ENABLED"] = "true"

    from api.main import app as real_app
    from shared.db import get_session_dependency
    import api.middleware.auth as auth_mod

    # Override DB session
    async def override_db():
        yield db_session

    # Inject test mock tokens into the auth middleware MOCK_USERS dict
    original_mock_users = auth_mod.MOCK_USERS.copy()
    auth_mod.MOCK_USERS.update(MOCK_TOKENS)

    real_app.dependency_overrides[get_session_dependency] = override_db
    yield real_app
    real_app.dependency_overrides.clear()
    auth_mod.MOCK_USERS = original_mock_users


@pytest_asyncio.fixture
async def client(app):
    """Async HTTP test client with admin auth token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.headers["Authorization"] = "Bearer test-admin-token"
        yield ac


@pytest_asyncio.fixture
async def client_no_auth(app):
    """Async HTTP test client with NO auth token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def client_user(app):
    """Async HTTP test client with client_user auth."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.headers["Authorization"] = "Bearer test-client-user-token"
        yield ac


# ---------------------------------------------------------------------------
# Seed data factories
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def seed_url(db_session):
    """Create and return a ComplianceRuleUrl."""
    url = ComplianceRuleUrl(
        id=uuid.uuid4(),
        name="Test eCFR PACE",
        url="https://www.ecfr.gov/test",
        description="Test regulation source",
        is_active=True,
    )
    db_session.add(url)
    await db_session.flush()
    return url


@pytest_asyncio.fixture
async def seed_scraped_content(db_session, seed_url):
    """Create and return a ScrapedContent linked to seed_url."""
    content = ScrapedContent(
        id=uuid.uuid4(),
        url_id=seed_url.id,
        content_text="Test regulatory content about PACE requirements.",
        content_hash="abc123",
        is_processed=True,
    )
    db_session.add(content)
    await db_session.flush()
    return content


@pytest_asyncio.fixture
async def seed_regulation(db_session, seed_scraped_content):
    """Create and return a Regulation linked to scraped content."""
    reg = Regulation(
        id=uuid.uuid4(),
        scraped_content_id=seed_scraped_content.id,
        source="ecfr",
        source_id="42-cfr-460-test",
        title="Test PACE Regulation — 42 CFR 460",
        summary="Test regulation about PACE program requirements.",
        relevance_score=0.95,
        status=RegulationStatus.FINAL_RULE,
        effective_date=date.today() + timedelta(days=90),
        affected_areas=["IDT", "Care Plan"],
        program_area=["PACE"],
        cfr_references=["42 CFR 460"],
        agencies=["CMS"],
        document_type="final_rule",
    )
    db_session.add(reg)
    await db_session.flush()
    return reg


@pytest_asyncio.fixture
async def seed_gaps(db_session, seed_scraped_content, seed_regulation):
    """Create and return a list of ComplianceGaps with varied severities."""
    gaps = []
    for i, (severity, status) in enumerate([
        (GapSeverity.CRITICAL, GapStatus.IDENTIFIED),
        (GapSeverity.HIGH, GapStatus.IN_PROGRESS),
        (GapSeverity.MEDIUM, GapStatus.IDENTIFIED),
        (GapSeverity.LOW, GapStatus.RESOLVED),
    ]):
        gap = ComplianceGap(
            id=uuid.uuid4(),
            scraped_content_id=seed_scraped_content.id,
            regulation_id=seed_regulation.id,
            title=f"Test Gap {i+1} ({severity.value})",
            description=f"Test description for gap {i+1}",
            severity=severity,
            status=status,
            affected_modules=["IDT", "Care Plan"] if i < 2 else ["Pharmacy"],
            affected_layer=AffectedLayer.BACKEND if i % 2 == 0 else AffectedLayer.FRONTEND,
            is_new_requirement=(i == 0),
        )
        gaps.append(gap)
        db_session.add(gap)

    await db_session.flush()
    return gaps


@pytest_asyncio.fixture
async def seed_tenant(db_session):
    """Create and return a Tenant."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Sunrise PACE",
        descope_tenant_id="tenant-001",
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest_asyncio.fixture
async def seed_pipeline_run(db_session):
    """Create and return a completed PipelineRun."""
    run = PipelineRun(
        id=uuid.uuid4(),
        run_type=PipelineRunType.ANALYSIS,
        status=PipelineRunStatus.COMPLETED,
        started_at=datetime.utcnow() - timedelta(minutes=5),
        ended_at=datetime.utcnow(),
        duration_seconds=300.0,
        regulations_added=5,
        gaps_added=3,
    )
    db_session.add(run)
    await db_session.flush()
    return run


@pytest_asyncio.fixture
async def seed_notification(db_session, seed_pipeline_run):
    """Create and return an AdminNotification."""
    notif = AdminNotification(
        id=uuid.uuid4(),
        pipeline_run_id=seed_pipeline_run.id,
        notification_type=NotificationType.PIPELINE_COMPLETED,
        title="Analysis Complete",
        message="Pipeline run completed with 5 regulations and 3 gaps.",
        is_read=False,
    )
    db_session.add(notif)
    await db_session.flush()
    return notif


@pytest_asyncio.fixture
async def seed_exec_report(db_session):
    """Create and return an ExecReport."""
    report = ExecReport(
        id=uuid.uuid4(),
        week_start=date.today() - timedelta(days=7),
        week_end=date.today() - timedelta(days=1),
        summary_html="<h1>Weekly Report</h1><p>5 new regulations, 3 gaps resolved.</p>",
        summary_plain="Weekly Report: 5 new regulations, 3 gaps resolved.",
        metrics={"new_regulations": 5, "gaps_identified": 8, "gaps_resolved": 3},
        risks=[{"title": "FHIR deadline", "severity": "high"}],
        highlights=["Resolved IDT gap", "Completed enrollment audit"],
    )
    db_session.add(report)
    await db_session.flush()
    return report


@pytest_asyncio.fixture
async def seed_gaps_for_scoring(db_session, seed_scraped_content):
    """Create gaps for compliance scoring tests: 2 resolved + 1 open in Pharmacy."""
    gaps = []
    for i, status in enumerate([GapStatus.RESOLVED, GapStatus.RESOLVED, GapStatus.IDENTIFIED]):
        gap = ComplianceGap(
            id=uuid.uuid4(),
            scraped_content_id=seed_scraped_content.id,
            title=f"Scoring Gap {i + 1}",
            description=f"Test gap {i + 1} for scoring",
            status=status,
            severity=GapSeverity.HIGH,
            affected_modules=["Pharmacy"],
            affected_layer=AffectedLayer.BACKEND,
        )
        db_session.add(gap)
        gaps.append(gap)
    await db_session.flush()
    return gaps



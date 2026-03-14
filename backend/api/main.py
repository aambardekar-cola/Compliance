"""FastAPI application entry point with Mangum handler for AWS Lambda."""
import logging
import os
from contextlib import asynccontextmanager

# Datadog APM — auto-instrument FastAPI, SQLAlchemy, httpx at import time
if os.environ.get("DD_TRACE_ENABLED") == "true":
    from ddtrace import patch_all
    patch_all()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum

from shared.config import get_settings
from shared.db import close_db
from shared import statsig_client
from api.middleware.auth import AuthMiddleware
from api.routes import dashboard, regulations, gaps, reports, subscriptions, admin, notifications, system_config

# ---- Logging ----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---- Lifespan ----
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    # Startup
    logger.info("Starting PaceCareOnline Compliance API")
    statsig_client.initialize()

    # Initialize DB schema for local/dev (SQLite — create_all is idempotent).
    # In production (PostgreSQL), schema is managed by migrations.
    settings = get_settings()
    if not settings.is_production:
        from shared.db import init_db
        await init_db()

    yield
    # Shutdown
    await close_db()
    statsig_client.shutdown()
    logger.info("Shutting down PaceCareOnline Compliance API")


# ---- FastAPI App ----
# Determine if API docs should be shown (Statsig gate overrides env check)
_show_docs = statsig_client.check_gate("api_docs_enabled") or not get_settings().is_production

app = FastAPI(
    title="PaceCareOnline Compliance Intelligence API",
    description="AI-powered compliance monitoring for PACE Market EHR",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if _show_docs else None,
    redoc_url="/api/redoc" if _show_docs else None,
)

# ---- Auth Middleware ----
app.add_middleware(AuthMiddleware)

# ---- CORS ----
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https://.*\.cloudfront\.net",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Routes ----
app.include_router(dashboard.router, tags=["Dashboard"])
app.include_router(regulations.router, tags=["Regulations"])
app.include_router(gaps.router, tags=["Gap Analysis"])

app.include_router(reports.router, tags=["Reports"])
app.include_router(subscriptions.router, tags=["Subscriptions"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(notifications.router, prefix="/admin", tags=["Notifications"])
app.include_router(system_config.router, prefix="/admin", tags=["System Config"])


# ---- Health Check (no auth) ----
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "pco-compliance-api", "version": "1.0.2"}


# ---- Error Handlers ----
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ---- Lambda Handler ----
handler = Mangum(app, lifespan="auto")

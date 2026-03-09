"""FastAPI application entry point with Mangum handler for AWS Lambda."""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum

from shared.config import get_settings
from shared.db import init_db, close_db
from api.middleware.auth import AuthMiddleware
from api.routes import dashboard, regulations, gaps, communications, reports, subscriptions, admin

from starlette.middleware.base import BaseHTTPMiddleware

class DebugMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            import traceback
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=500, content={"detail": "CRASH", "trace": traceback.format_exc()})

# ---- Logging ----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- FastAPI App ----
app = FastAPI(
    title="PaceCareOnline Compliance Intelligence API",
    description="AI-powered compliance monitoring for PACE Market EHR",
    version="1.0.0",
    docs_url="/api/docs" if not get_settings().is_production else None,
    redoc_url="/api/redoc" if not get_settings().is_production else None,
)

# ---- Auth Middleware ----
app.add_middleware(DebugMiddleware)
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
app.include_router(communications.router, tags=["Communications"])
app.include_router(reports.router, tags=["Reports"])
app.include_router(subscriptions.router, tags=["Subscriptions"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])


# ---- Lifecycle Events ----
@app.on_event("startup")
async def startup():
    logger.info("Starting PaceCareOnline Compliance API")


@app.on_event("shutdown")
async def shutdown():
    await close_db()
    logger.info("Shutting down PaceCareOnline Compliance API")


# ---- Health Check (no auth) ----
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "pco-compliance-api", "version": "1.0.0"}


# ---- Error Handlers ----
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ---- Lambda Handler ----
handler = Mangum(app, lifespan="off")

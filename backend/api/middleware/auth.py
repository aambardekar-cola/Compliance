"""FastAPI authentication middleware using Descope."""
import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from shared.auth import validate_token, CurrentUser

logger = logging.getLogger(__name__)

# Paths that don't require authentication
PUBLIC_PATHS = {
    "/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
}


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that validates Descope JWT tokens on protected routes."""

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public endpoints and preflight requests
        if request.url.path in PUBLIC_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header"},
            )

        token = auth_header[7:]  # Remove 'Bearer '

        try:
            user = validate_token(token)
            # Attach user to request state for use in route handlers
            request.state.user = user
        except Exception as e:
            logger.warning(f"Auth failed for {request.url.path}: {e}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )

        return await call_next(request)


def get_current_user(request: Request) -> CurrentUser:
    """FastAPI dependency to get the authenticated user from request state.

    Usage in routes:
        @router.get("/endpoint")
        async def my_endpoint(user: CurrentUser = Depends(get_current_user)):
            ...
    """
    user = getattr(request.state, "user", None)
    if user is None:
        raise Exception("User not found in request state")
    return user

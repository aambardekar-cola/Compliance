"""FastAPI authentication middleware using Descope."""
import logging
import os

from fastapi import Request, Depends, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from shared.auth import validate_token, CurrentUser
from shared import statsig_client

logger = logging.getLogger(__name__)

# Paths that don't require authentication
PUBLIC_PATHS = {
    "/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
}

# Module-level mock user definitions (avoids recreating on every request)
MOCK_USERS = {
    "mock-admin-token": CurrentUser(
        user_id="mock-admin-123", email="admin@collabrios.com", name="Sarah Mitchell",
        tenant_id=None, tenant_name=None, roles=["internal_admin"], permissions=[]
    ),
    "mock-internal-token": CurrentUser(
        user_id="mock-internal-456", email="dev@collabrios.com", name="James Reeves",
        tenant_id=None, tenant_name=None, roles=["internal_user"], permissions=[]
    ),
    "mock-client-admin-token": CurrentUser(
        user_id="mock-client-789", email="admin@sunrisepace.org", name="Maria Santos",
        tenant_id="tenant-custom-001", tenant_name="Sunrise PACE", roles=["client_admin"], permissions=[]
    ),
    "mock-client-user-token": CurrentUser(
        user_id="mock-client-abc", email="nurse@sunrisepace.org", name="David Chen",
        tenant_id="tenant-custom-001", tenant_name="Sunrise PACE", roles=["client_user"], permissions=[]
    ),
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

        # --- Demo Mode / Mock Token Support ---
        # Controlled by Statsig gate OR MOCK_AUTH_ENABLED env var (fallback)
        mock_auth_enabled = (
            statsig_client.check_gate("mock_auth_bypass")
            or os.environ.get("MOCK_AUTH_ENABLED", "").lower() == "true"
        )

        if mock_auth_enabled and token in MOCK_USERS:
            logger.info("Mock auth bypass: user=%s path=%s", MOCK_USERS[token].email, request.url.path)
            request.state.user = MOCK_USERS[token]
            return await call_next(request)

        # --- Real Descope Auth ---
        try:
            user = validate_token(token)
            request.state.user = user
        except Exception as e:
            logger.warning("Auth failed for %s: %s", request.url.path, e)
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
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_role(roles: list[str]):
    """FastAPI dependency factory to assert the current user has at least one of the specified roles."""
    def role_dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        # Normalize to list if a single enum/string was passed
        roles_list = roles if isinstance(roles, list) else [roles]
        # Convert provided roles to their string values if they are Enums
        allowed_roles = [r.value if hasattr(r, "value") else str(r) for r in roles_list]
        logger.debug("Role check: user.roles=%s, allowed_roles=%s", user.roles, allowed_roles)
        if not any(role in user.roles for role in allowed_roles):
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return user
    return role_dependency

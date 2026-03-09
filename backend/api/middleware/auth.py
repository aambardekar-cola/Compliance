"""FastAPI authentication middleware using Descope."""
import logging

from fastapi import Request, Depends
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

        # --- Demo Mode / Mock Token Support ---
        # NEVER allow mock tokens in production!
        settings = get_settings()
        is_prod = settings.app_env in ("prod", "production")
        
        mock_users = {
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

        if not is_prod and token in mock_users:
            request.state.user = mock_users[token]
            return await call_next(request)
        
        # --- Real Descope Auth ---
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


def require_role(roles: list[str]):
    """FastAPI dependency factory to assert the current user has at least one of the specified roles."""
    def role_dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        # Normalize to list if a single enum/string was passed
        roles_list = roles if isinstance(roles, list) else [roles]
        # Convert provided roles to their string values if they are Enums
        allowed_roles = [r.value if hasattr(r, "value") else str(r) for r in roles_list]
        print(f"DEBUG: user.roles={user.roles}, allowed_roles={allowed_roles}")
        if not any(role in user.roles for role in allowed_roles):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return user
    return role_dependency

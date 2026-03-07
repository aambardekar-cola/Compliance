"""Descope authentication utilities."""
import logging
from dataclasses import dataclass

import jwt
from descope import DescopeClient, AuthException

from shared.config import get_settings

logger = logging.getLogger(__name__)

_descope_client = None


@dataclass
class CurrentUser:
    """Represents the authenticated user from a Descope JWT."""
    user_id: str
    email: str
    name: str
    tenant_id: str | None
    tenant_name: str | None
    roles: list[str]
    permissions: list[str]

    @property
    def is_internal(self) -> bool:
        """Check if user is an internal Collabrios staff member."""
        return "internal_admin" in self.roles or "internal_user" in self.roles

    @property
    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return "internal_admin" in self.roles or "client_admin" in self.roles


def get_descope_client() -> DescopeClient:
    """Get or create the Descope client."""
    global _descope_client
    if _descope_client is None:
        settings = get_settings()
        _descope_client = DescopeClient(
            project_id=settings.descope_project_id,
            management_key=settings.descope_management_key or None,
        )
    return _descope_client


def validate_token(token: str) -> CurrentUser:
    """Validate a Descope JWT and extract user information.

    Args:
        token: The JWT bearer token (without 'Bearer ' prefix)

    Returns:
        CurrentUser with extracted claims

    Raises:
        AuthException: If token is invalid
    """
    try:
        client = get_descope_client()
        jwt_response = client.validate_session(token)

        claims = jwt_response.get("jwt", {})
        token_claims = jwt_response.get("token", {})

        # Extract tenant information from Descope
        tenants = claims.get("tenants", {})
        tenant_id = None
        tenant_name = None
        roles = []
        permissions = []

        if tenants:
            # Use the first tenant (users typically belong to one tenant)
            first_tenant_id = list(tenants.keys())[0]
            tenant_data = tenants[first_tenant_id]
            tenant_id = first_tenant_id
            tenant_name = tenant_data.get("name", "")
            roles = tenant_data.get("roles", [])
            permissions = tenant_data.get("permissions", [])
        else:
            # Fallback to top-level roles (internal users)
            roles = claims.get("roles", [])
            permissions = claims.get("permissions", [])

        return CurrentUser(
            user_id=claims.get("sub", ""),
            email=claims.get("email", ""),
            name=claims.get("name", ""),
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            roles=roles,
            permissions=permissions,
        )
    except AuthException as e:
        logger.warning(f"Token validation failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during token validation: {e}")
        raise AuthException(
            status_code=401,
            error_type="invalid_token",
            error_description="Failed to validate token",
            error_message=str(e),
        )


def decode_token_unverified(token: str) -> dict:
    """Decode a JWT without verification (for logging/debugging only)."""
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except Exception:
        return {}

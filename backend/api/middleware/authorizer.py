"""API Gateway Lambda Authorizer for Descope JWT tokens."""
import json
import logging
import os

from shared.auth import validate_token

logger = logging.getLogger(__name__)


def handler(event, context):
    """Lambda authorizer handler for API Gateway.

    Validates the Descope JWT and returns an IAM policy
    allowing or denying access to the API.
    """
    token = event.get("authorizationToken", "")

    # Remove "Bearer " prefix if present
    if token.startswith("Bearer "):
        token = token[7:]

    if not token:
        logger.warning("No token provided")
        raise Exception("Unauthorized")

    try:
        user = validate_token(token)

        # Build the IAM policy
        method_arn = event.get("methodArn", "")
        # Allow access to all methods on this API
        arn_parts = method_arn.split(":")
        api_gateway_arn = ":".join(arn_parts[:5])
        rest_api_path = arn_parts[5].split("/")
        api_id = rest_api_path[0]
        stage = rest_api_path[1]

        resource_arn = f"{api_gateway_arn}:{api_id}/{stage}/*/*"

        policy = {
            "principalId": user.user_id,
            "policyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": "execute-api:Invoke",
                        "Effect": "Allow",
                        "Resource": resource_arn,
                    }
                ],
            },
            "context": {
                "user_id": user.user_id,
                "email": user.email,
                "name": user.name,
                "tenant_id": user.tenant_id or "",
                "roles": json.dumps(user.roles),
                "is_internal": str(user.is_internal),
            },
        }

        logger.info(f"Authorized user {user.email} (tenant: {user.tenant_id})")
        return policy

    except Exception as e:
        logger.warning(f"Authorization failed: {e}")
        raise Exception("Unauthorized")

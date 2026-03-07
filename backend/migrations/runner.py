"""Lambda handler for running Alembic database migrations.

This Lambda runs inside the VPC with access to Aurora via RDS Proxy.
It resolves the database URL from Secrets Manager and runs Alembic
programmatically.

Invocation:
    aws lambda invoke --function-name <migration-lambda-name> \
        --payload '{"command": "upgrade", "revision": "head"}' out.json
"""
import json
import logging
import os
import subprocess
import sys

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_database_url() -> str:
    """Build the database URL from Secrets Manager + RDS Proxy endpoint."""
    secret_arn = os.environ["DB_SECRET_ARN"]
    proxy_endpoint = os.environ["DB_PROXY_ENDPOINT"]

    client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-2"))
    response = client.get_secret_value(SecretId=secret_arn)
    secret = json.loads(response["SecretString"])

    username = secret["username"]
    password = secret["password"]
    database = secret.get("dbname", "compliance_db")

    # Use psycopg2 (synchronous) for Alembic migrations instead of asyncpg
    return f"postgresql://{username}:{password}@{proxy_endpoint}:5432/{database}"


def handler(event, context):
    """Lambda handler that runs Alembic migrations.

    Args:
        event: {
            "command": "upgrade" | "downgrade" | "current" | "history",
            "revision": "head" | specific revision (default: "head")
        }
    """
    command = event.get("command", "upgrade")
    revision = event.get("revision", "head")

    logger.info(f"Running alembic {command} {revision}")

    try:
        database_url = get_database_url()
        logger.info(f"Database URL resolved (host: {os.environ['DB_PROXY_ENDPOINT']})")

        # Set the database URL for Alembic's env.py to pick up
        os.environ["DATABASE_URL"] = database_url

        # Change to the backend directory where alembic.ini lives
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os.chdir(backend_dir)

        # Run alembic programmatically
        from alembic.config import Config
        from alembic import command as alembic_cmd

        alembic_cfg = Config("alembic.ini")
        # Override the URL with the resolved one
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)

        if command == "upgrade":
            alembic_cmd.upgrade(alembic_cfg, revision)
            message = f"Successfully upgraded to {revision}"
        elif command == "downgrade":
            alembic_cmd.downgrade(alembic_cfg, revision)
            message = f"Successfully downgraded to {revision}"
        elif command == "current":
            alembic_cmd.current(alembic_cfg)
            message = "Current revision displayed in logs"
        elif command == "history":
            alembic_cmd.history(alembic_cfg)
            message = "History displayed in logs"
        elif command == "seed":
            # Seed demo data
            import asyncio
            from scripts.seed_demo_data import seed_demo_data
            
            # Since the global event loop might not be set up correctly in lambda,
            # we use asyncio.run to execute the async seeding function.
            asyncio.run(seed_demo_data())
            message = "Demo data successfully seeded"
        else:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Unknown command: {command}"}),
            }

        logger.info(message)
        return {
            "statusCode": 200,
            "body": json.dumps({"message": message}),
        }

    except Exception as e:
        logger.error(f"Migration/Seeding failed: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }

#!/usr/bin/env bash
# Build the Lambda layer with Python dependencies.
# This script installs pip packages into backend/layer/python/
# which CDK packages as a Lambda Layer.
set -euo pipefail

LAYER_DIR="$(dirname "$0")/../backend/layer/python"

echo "→ Building Lambda layer..."
rm -rf "$(dirname "$0")/../backend/layer"
mkdir -p "$LAYER_DIR"

pip3 install \
    --target "$LAYER_DIR" \
    --platform manylinux2014_aarch64 \
    --implementation cp \
    --python-version 3.12 \
    --only-binary=:all: \
    fastapi mangum uvicorn \
    sqlalchemy asyncpg psycopg2-binary alembic \
    pydantic pydantic-settings pydantic-core \
    httpx python-dateutil \
    boto3 \
    pyjwt cryptography \
    descope \
    typing_extensions annotated-types \
    anyio sniffio idna certifi \
    starlette Mako MarkupSafe \
    2>&1 | tail -5

# Also install packages that may not have pre-built wheels
pip3 install \
    --target "$LAYER_DIR" \
    --platform manylinux2014_aarch64 \
    --implementation cp \
    --python-version 3.12 \
    --only-binary=:none: \
    --no-deps \
    structlog greenlet \
    2>/dev/null || pip3 install --target "$LAYER_DIR" --no-deps structlog greenlet

echo "✓ Layer built at: $LAYER_DIR"
echo "  Size: $(du -sh "$LAYER_DIR" | cut -f1)"

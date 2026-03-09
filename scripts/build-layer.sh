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
    pyjwt cryptography \
    descope \
    typing_extensions annotated-types \
    anyio sniffio idna certifi \
    starlette Mako MarkupSafe \
    beautifulsoup4 lxml \
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

echo "→ Trimming package size..."
find "$LAYER_DIR" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "$LAYER_DIR" -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
find "$LAYER_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$LAYER_DIR" -name "*.so" -exec strip {} + 2>/dev/null || true
rm -rf "$LAYER_DIR/boto3" "$LAYER_DIR/botocore" "$LAYER_DIR/s3transfer" 2>/dev/null || true

echo "✓ Layer built at: $LAYER_DIR"
echo "  Size: $(du -sh "$LAYER_DIR" | cut -f1)"

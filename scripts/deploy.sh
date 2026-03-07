#!/usr/bin/env bash
# ==============================================================================
# CDK Deploy Wrapper
# Usage: ./scripts/deploy.sh [dev|staging|prod]
# ==============================================================================
set -euo pipefail

ENV="${1:-dev}"

echo "=============================================="
echo " Deploying PCO Compliance — ${ENV}"
echo "=============================================="

# Validate environment
if [[ ! "$ENV" =~ ^(dev|staging|prod)$ ]]; then
    echo "ERROR: Invalid environment '$ENV'. Must be dev, staging, or prod."
    exit 1
fi

# Validate AWS credentials are set
if [[ -z "${AWS_ACCESS_KEY_ID:-}" || -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
    echo "ERROR: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set."
    exit 1
fi

export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

# Build frontend
echo ""
echo "→ Building frontend..."
cd "$(dirname "$0")/../frontend"
npm ci --no-audit --no-fund --loglevel=error
npm run build
echo "✓ Frontend built"

# Deploy CDK stacks
echo ""
echo "→ Deploying CDK stacks for env: ${ENV}..."
cd "$(dirname "$0")/../infrastructure"
pip install -q -r requirements.txt 2>/dev/null

cdk deploy --all \
    -c env="${ENV}" \
    --require-approval never \
    --outputs-file cdk-outputs.json

echo ""
echo "✓ CDK deploy complete"
echo ""

# Show outputs
if [[ -f cdk-outputs.json ]]; then
    echo "Stack Outputs:"
    cat cdk-outputs.json
fi

# Invalidate CloudFront cache
echo ""
echo "→ Invalidating CloudFront cache..."
cd "$(dirname "$0")/.."
bash scripts/invalidate-cache.sh "${ENV}"

echo ""
echo "=============================================="
echo " Deploy to ${ENV} complete!"
echo "=============================================="

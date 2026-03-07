#!/usr/bin/env bash
# ==============================================================================
# CloudFront Cache Invalidation
# Usage: ./scripts/invalidate-cache.sh [dev|staging|prod]
# ==============================================================================
set -euo pipefail

ENV="${1:-dev}"
INFRA_DIR="$(dirname "$0")/../infrastructure"
OUTPUTS_FILE="${INFRA_DIR}/cdk-outputs.json"

# Stack name pattern — matches the naming convention in app.py
STACK_NAME="pco-compliance-${ENV}-frontend"

if [[ ! -f "$OUTPUTS_FILE" ]]; then
    echo "⚠ No cdk-outputs.json found — skipping CloudFront invalidation."
    echo "  Run 'cdk deploy' first to generate outputs."
    exit 0
fi

# Extract the CloudFront distribution domain from CDK outputs
DISTRIBUTION_DOMAIN=$(python3 -c "
import json, sys
with open('${OUTPUTS_FILE}') as f:
    outputs = json.load(f)
stack = outputs.get('${STACK_NAME}', {})
domain = stack.get('DistributionDomainName', '')
print(domain)
" 2>/dev/null || echo "")

if [[ -z "$DISTRIBUTION_DOMAIN" ]]; then
    echo "⚠ Could not find CloudFront distribution in outputs — skipping invalidation."
    exit 0
fi

# Get distribution ID from the domain
DISTRIBUTION_ID=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?DomainName=='${DISTRIBUTION_DOMAIN}'].Id" \
    --output text 2>/dev/null || echo "")

if [[ -z "$DISTRIBUTION_ID" || "$DISTRIBUTION_ID" == "None" ]]; then
    echo "⚠ Could not resolve distribution ID — skipping invalidation."
    exit 0
fi

echo "→ Invalidating CloudFront distribution: ${DISTRIBUTION_ID}"
aws cloudfront create-invalidation \
    --distribution-id "$DISTRIBUTION_ID" \
    --paths "/*" \
    --query "Invalidation.Id" \
    --output text

echo "✓ CloudFront cache invalidation created"

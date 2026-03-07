#!/usr/bin/env bash
# ==============================================================================
# Run Database Migrations via Lambda
# Usage: ./scripts/run-migrations.sh [dev|staging|prod]
# ==============================================================================
set -euo pipefail

ENV="${1:-dev}"
INFRA_DIR="$(dirname "$0")/../infrastructure"
OUTPUTS_FILE="${INFRA_DIR}/cdk-outputs.json"
STACK_NAME="pco-compliance-${ENV}-data"

if [[ ! -f "$OUTPUTS_FILE" ]]; then
    echo "⚠ No cdk-outputs.json found — skipping migration."
    exit 0
fi

# Extract migration Lambda ARN from CDK outputs
MIGRATION_ARN=$(python3 -c "
import json
with open('${OUTPUTS_FILE}') as f:
    outputs = json.load(f)
stack = outputs.get('${STACK_NAME}', {})
arn = stack.get('MigrationLambdaArn', '')
print(arn)
" 2>/dev/null || echo "")

if [[ -z "$MIGRATION_ARN" ]]; then
    echo "⚠ Could not find migration Lambda ARN in outputs — skipping."
    exit 0
fi

# Extract just the function name from the ARN
FUNCTION_NAME=$(echo "$MIGRATION_ARN" | awk -F: '{print $NF}')

echo "→ Running database migrations via Lambda: ${FUNCTION_NAME}"
RESPONSE=$(aws lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --payload '{"command": "upgrade", "revision": "head"}' \
    --cli-binary-format raw-in-base64-out \
    /tmp/migration-response.json \
    --query 'StatusCode' \
    --output text 2>&1)

echo "  Lambda status code: ${RESPONSE}"

if [[ -f /tmp/migration-response.json ]]; then
    BODY=$(cat /tmp/migration-response.json)
    echo "  Response: ${BODY}"

    # Check if the migration failed
    STATUS_CODE=$(echo "$BODY" | python3 -c "import json,sys; print(json.load(sys.stdin).get('statusCode', 0))" 2>/dev/null || echo "0")
    if [[ "$STATUS_CODE" == "500" ]]; then
        echo "❌ Migration failed!"
        exit 1
    fi
fi

echo "✓ Database migrations complete"

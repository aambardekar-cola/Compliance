"""Statsig setup automation — creates all feature gates, dynamic configs,
experiments, and tags via the Statsig Console API.

Usage:
    export STATSIG_CONSOLE_KEY="console-..."
    python infrastructure/scripts/setup_statsig.py
"""
import os
import sys

try:
    import requests
except ImportError:
    print("ERROR: requests library required. Install via: pip install requests")
    sys.exit(1)

CONSOLE_KEY = os.environ.get("STATSIG_CONSOLE_KEY", "")
BASE_URL = "https://statsigapi.net/console/v1"

HEADERS = {
    "STATSIG-API-KEY": CONSOLE_KEY,
    "Content-Type": "application/json",
}


# ──────────────────────────────────────────────
# Tag Definitions
# ──────────────────────────────────────────────

TAGS = [
    "ai-pipeline",
    "scraper",
    "api-behavior",
    "infrastructure",
    "auth",
    "datadog",
    "experiment",
    "security-sensitive",
]


# ──────────────────────────────────────────────
# Feature Gate Definitions
# ──────────────────────────────────────────────

GATES = [
    {
        "name": "demo_mode",
        "description": "Enables demo login flow with mock users — no real auth required.",
        "tags": ["auth"],
    },
    {
        "name": "force_demo_mode",
        "description": "Forces demo mode even when Descope is configured.",
        "tags": ["auth"],
    },
    {
        "name": "mock_auth_bypass",
        "description": "SECURITY-SENSITIVE: Allows API calls without real auth tokens. NEVER enable in production.",
        "tags": ["auth", "security-sensitive"],
    },
    {
        "name": "api_docs_enabled",
        "description": "Shows /api/docs Swagger UI. Exposes API schema when enabled.",
        "tags": ["auth"],
    },
    {
        "name": "dd_trace_enabled",
        "description": "Master switch for Datadog APM tracing. Disabling drops all traces.",
        "tags": ["datadog"],
    },
    {
        "name": "dd_capture_payload",
        "description": "Logs Lambda event payload in Datadog traces. Useful for debugging but has PII risk.",
        "tags": ["datadog", "security-sensitive"],
    },
    {
        "name": "dd_serverless_logs",
        "description": "Sends Lambda logs to Datadog. Affects log ingestion cost.",
        "tags": ["datadog"],
    },
]


# ──────────────────────────────────────────────
# Dynamic Config Definitions
# ──────────────────────────────────────────────

CONFIGS = [
    {
        "name": "ai_models",
        "description": "AI pipeline model IDs and parameters. Controls which Bedrock models are used for analysis.",
        "tags": ["ai-pipeline"],
        "value": {
            "haiku_model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            "sonnet_model_id": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "default_model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "max_tokens": 4096,
            "temperature": 0.3,
            "max_content_chars": 50000,
            "max_chunks_per_run": 10,
            "bedrock_read_timeout": 300,
            "bedrock_max_retries": 2,
        },
    },
    {
        "name": "pco_modules",
        "description": "Canonical list of PCO software modules for gap analysis matching.",
        "tags": ["ai-pipeline"],
        "value": {
            "modules": [
                "IDT", "Care Plan", "Pharmacy", "Enrollment", "Claims",
                "Transportation", "Quality", "Billing", "Authorization",
                "Member Services", "Provider Network", "Reporting",
                "Compliance Dashboard",
            ],
        },
    },
    {
        "name": "pagination",
        "description": "Page sizes for API endpoints. Controls items per page in the frontend.",
        "tags": ["api-behavior"],
        "value": {
            "regulations_page_size": 20,
            "gaps_page_size": 20,
            "reports_page_size": 10,
            "communications_page_size": 20,
            "notifications_page_size": 20,
        },
    },
    {
        "name": "scraper",
        "description": "Scraper HTTP settings. Changes User-Agent and Accept headers for .gov compatibility.",
        "tags": ["scraper"],
        "value": {
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 PaceCareOnline/1.0"
            ),
        },
    },
    {
        "name": "ingestion",
        "description": "Ingestion pipeline settings. Controls relevance scoring thresholds.",
        "tags": ["ai-pipeline"],
        "value": {
            "relevance_threshold": 0.3,
        },
    },
    {
        "name": "database",
        "description": "Database connection pool settings. Affects concurrent query capacity.",
        "tags": ["api-behavior"],
        "value": {
            "pool_size": 5,
            "max_overflow": 10,
            "pool_recycle": 300,
        },
    },
    {
        "name": "dashboard",
        "description": "Dashboard display settings. Controls relevance thresholds and deadline windows.",
        "tags": ["api-behavior"],
        "value": {
            "relevance_threshold": 0.5,
            "deadlines_window_days": 90,
            "deadlines_limit": 10,
            "stale_run_cleanup_minutes": 10,
        },
    },
    {
        "name": "datadog",
        "description": "Datadog observability settings. Controls trace sampling and RUM config.",
        "tags": ["datadog"],
        "value": {
            "trace_sample_rate": 0.1,
            "trace_ignore_resources": "/health",
            "rum_session_sample_rate": 100,
            "rum_replay_sample_rate": 20,
            "rum_privacy_level": "mask-user-input",
        },
    },
    {
        "name": "infrastructure_reference",
        "description": "READ-ONLY — These are CDK deploy-time values. Changing them here does NOT take effect. Change via CDK deploy.",
        "tags": ["infrastructure"],
        "value": {
            "api_lambda_memory_mb": 512,
            "api_lambda_timeout_s": 30,
            "pipeline_lambda_memory_mb": 1024,
            "scraper_lambda_timeout_min": 10,
            "analysis_lambda_timeout_min": 15,
            "sqs_dlq_retry_count": 3,
            "sqs_visibility_timeout_min": 15,
            "dlq_retention_days": 14,
            "sqs_batch_size": 1,
        },
    },
]


# ──────────────────────────────────────────────
# Experiment Definitions
# ──────────────────────────────────────────────

EXPERIMENTS = [
    {
        "name": "llm_temperature",
        "description": "A/B test LLM temperature for regulation extraction quality.",
        "tags": ["ai-pipeline", "experiment"],
    },
    {
        "name": "relevance_threshold",
        "description": "A/B test relevance score cutoff for ingestion filtering.",
        "tags": ["ai-pipeline", "experiment"],
    },
    {
        "name": "regulation_page_size",
        "description": "A/B test page size on regulations list (20 vs 30).",
        "tags": ["api-behavior", "experiment"],
    },
    {
        "name": "gap_page_size",
        "description": "A/B test page size on gap analysis list.",
        "tags": ["api-behavior", "experiment"],
    },
    {
        "name": "report_page_size",
        "description": "A/B test page size on reports list.",
        "tags": ["api-behavior", "experiment"],
    },
    {
        "name": "dashboard_relevance",
        "description": "A/B test dashboard relevance threshold (0.5 vs 0.7).",
        "tags": ["api-behavior", "experiment"],
    },
]


# ──────────────────────────────────────────────
# API Helpers
# ──────────────────────────────────────────────

def api_post(endpoint: str, payload: dict) -> dict:
    """Make a POST request to Statsig Console API."""
    resp = requests.post(f"{BASE_URL}{endpoint}", headers=HEADERS, json=payload, timeout=30)
    if resp.status_code in (200, 201):
        print(f"  ✅ Created: {endpoint}")
        return resp.json()
    elif resp.status_code == 409:
        print(f"  ⏭️  Already exists: {endpoint}")
        return {}
    else:
        print(f"  ❌ Failed ({resp.status_code}): {endpoint} — {resp.text}")
        return {}


def create_tags():
    """Create all tags."""
    print("\n📌 Creating tags...")
    for tag in TAGS:
        api_post("/tags", {"name": tag, "description": f"PCO Compliance: {tag}"})


def create_gates():
    """Create all feature gates."""
    print("\n🚩 Creating feature gates...")
    for gate in GATES:
        api_post("/gates", gate)


def create_configs():
    """Create all dynamic configs."""
    print("\n⚙️  Creating dynamic configs...")
    for config in CONFIGS:
        api_post("/dynamic_configs", config)


def create_experiments():
    """Create all experiments (inactive — need manual activation in console)."""
    print("\n🔬 Creating experiments...")
    for exp in EXPERIMENTS:
        api_post("/experiments", exp)


def main():
    """Run full Statsig setup."""
    if not CONSOLE_KEY:
        print("ERROR: Set STATSIG_CONSOLE_KEY environment variable")
        sys.exit(1)

    print("=" * 60)
    print("🚀 PCO Compliance — Statsig Setup")
    print("=" * 60)

    create_tags()
    create_gates()
    create_configs()
    create_experiments()

    print("\n" + "=" * 60)
    print("✅ Setup complete!")
    print(f"   Tags: {len(TAGS)}")
    print(f"   Gates: {len(GATES)}")
    print(f"   Configs: {len(CONFIGS)}")
    print(f"   Experiments: {len(EXPERIMENTS)}")
    print("=" * 60)
    print("\n📋 Next steps:")
    print("   1. Open Statsig Console → Feature Gates → Set per-environment rules")
    print("   2. Open Statsig Console → Experiments → Configure variants + start")
    print("   3. Verify SDK integration in dev environment")


if __name__ == "__main__":
    main()

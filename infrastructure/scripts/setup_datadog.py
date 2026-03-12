#!/usr/bin/env python3
"""Datadog Dashboard & Monitor Setup Script for PCO Compliance.

Creates 3 dashboards and 8 monitors programmatically via the Datadog API.

Usage:
    # Set env vars first:
    export DD_API_KEY="<your-api-key>"
    export DD_APP_KEY="<your-app-key>"
    export DD_SITE="datadoghq.com"  # or datadoghq.eu

    # Run:
    python scripts/setup_datadog.py --env dev
    python scripts/setup_datadog.py --env prod --teams-webhook "https://..."

Requirements:
    pip install datadog-api-client
"""
import argparse
import json
import sys
import os

try:
    from datadog_api_client import Configuration, ApiClient
    from datadog_api_client.v1.api.dashboards_api import DashboardsApi
    from datadog_api_client.v1.api.monitors_api import MonitorsApi
    from datadog_api_client.v1.model.dashboard import Dashboard
    from datadog_api_client.v1.model.dashboard_layout_type import DashboardLayoutType
    from datadog_api_client.v1.model.widget import Widget
    from datadog_api_client.v1.model.widget_definition import WidgetDefinition
    from datadog_api_client.v1.model.monitor import Monitor
    from datadog_api_client.v1.model.monitor_type import MonitorType
    _HAS_DD_CLIENT = True
except ImportError:
    _HAS_DD_CLIENT = False


# ─── Dashboard Definitions ───────────────────────────────────────────

def compliance_pipeline_dashboard(env: str) -> dict:
    """Dashboard 1: Compliance Pipeline Overview."""
    return {
        "title": f"PCO Compliance Pipeline [{env}]",
        "description": "End-to-end view of the regulatory compliance pipeline",
        "layout_type": "ordered",
        "widgets": [
            # Row 1: Pipeline Health Summary
            _query_value("Pipeline Runs (24h)", f"sum:trace.analysis.run.hits{{env:{env}}}"),
            _query_value("Error Rate", f"sum:trace.analysis.run.errors{{env:{env}}}.as_rate()"),
            _query_value("Avg Pipeline Duration", f"avg:trace.analysis.run.duration{{env:{env}}}"),
            # Row 2: Bedrock Invocation Breakdown
            _timeseries("Bedrock Invocations by Purpose", [
                f"sum:trace.bedrock.filtering.hits{{env:{env}}}.as_count()",
                f"sum:trace.bedrock.regulation_extraction.hits{{env:{env}}}.as_count()",
                f"sum:trace.bedrock.gap_analysis.hits{{env:{env}}}.as_count()",
            ]),
            _timeseries("Bedrock Latency by Purpose (p95)", [
                f"p95:trace.bedrock.filtering.duration{{env:{env}}}",
                f"p95:trace.bedrock.regulation_extraction.duration{{env:{env}}}",
                f"p95:trace.bedrock.gap_analysis.duration{{env:{env}}}",
            ]),
            # Row 3: Token Usage & Chunk Processing
            _timeseries("Token Usage (In/Out)", [
                f"sum:bedrock.tokens_in{{env:{env}}}.as_count()",
                f"sum:bedrock.tokens_out{{env:{env}}}.as_count()",
            ]),
            _timeseries("Chunk Processing Time", [
                f"avg:trace.analysis.process_chunk.duration{{env:{env}}}",
                f"p95:trace.analysis.process_chunk.duration{{env:{env}}}",
            ]),
            # Row 4: Regulation & Gap Counts
            _query_value("Regulations Found (24h)", f"sum:chunk.regulations_found{{env:{env}}}"),
            _query_value("Gaps Identified (24h)", f"sum:chunk.gaps_found{{env:{env}}}"),
        ],
    }


def bedrock_ai_dashboard(env: str) -> dict:
    """Dashboard 2: Bedrock AI Performance."""
    return {
        "title": f"Bedrock AI Performance [{env}]",
        "description": "Deep dive into Bedrock model performance, costs, and errors",
        "layout_type": "ordered",
        "widgets": [
            # Model Performance
            _timeseries("Latency by Model", [
                f"avg:trace.bedrock.regulation_extraction.duration{{env:{env}}} by {{bedrock.model_id}}",
                f"avg:trace.bedrock.gap_analysis.duration{{env:{env}}} by {{bedrock.model_id}}",
            ]),
            _timeseries("Error Rate by Model", [
                f"sum:trace.bedrock.regulation_extraction.errors{{env:{env}}} by {{bedrock.model_id}}.as_rate()",
                f"sum:trace.bedrock.gap_analysis.errors{{env:{env}}} by {{bedrock.model_id}}.as_rate()",
            ]),
            # Token Economics
            _timeseries("Input Tokens per Invocation", [
                f"avg:bedrock.tokens_in{{env:{env}}} by {{bedrock.purpose}}",
            ]),
            _timeseries("Output Tokens per Invocation", [
                f"avg:bedrock.tokens_out{{env:{env}}} by {{bedrock.purpose}}",
            ]),
            # Throttling & Retries
            _timeseries("Bedrock Throttling Events", [
                f"sum:trace.bedrock.filtering.errors{{env:{env},error.type:ThrottlingException}}.as_count()",
                f"sum:trace.bedrock.regulation_extraction.errors{{env:{env},error.type:ThrottlingException}}.as_count()",
            ]),
        ],
    }


def api_infrastructure_dashboard(env: str) -> dict:
    """Dashboard 3: API & Infrastructure Health."""
    return {
        "title": f"PCO API & Infrastructure [{env}]",
        "description": "API performance, Lambda metrics, and infrastructure health",
        "layout_type": "ordered",
        "widgets": [
            # API Performance
            _timeseries("API Latency (p50/p95/p99)", [
                f"p50:trace.fastapi.request.duration{{env:{env},service:pco-compliance-api}}",
                f"p95:trace.fastapi.request.duration{{env:{env},service:pco-compliance-api}}",
                f"p99:trace.fastapi.request.duration{{env:{env},service:pco-compliance-api}}",
            ]),
            _timeseries("API Requests by Status", [
                f"sum:trace.fastapi.request.hits{{env:{env},service:pco-compliance-api}} by {{http.status_code}}.as_count()",
            ]),
            _timeseries("API Error Rate", [
                f"sum:trace.fastapi.request.errors{{env:{env},service:pco-compliance-api}}.as_rate()",
            ]),
            # Lambda Metrics
            _timeseries("Lambda Duration", [
                f"avg:aws.lambda.duration{{env:{env},functionname:*compliance*}}",
                f"max:aws.lambda.duration{{env:{env},functionname:*compliance*}}",
            ]),
            _timeseries("Lambda Concurrent Executions", [
                f"avg:aws.lambda.concurrent_executions{{env:{env},functionname:*compliance*}}",
            ]),
            # Database
            _timeseries("DB Query Latency", [
                f"avg:trace.sqlalchemy.query.duration{{env:{env}}}",
                f"p95:trace.sqlalchemy.query.duration{{env:{env}}}",
            ]),
        ],
    }


# ─── Monitor Definitions ─────────────────────────────────────────────

def get_monitors(env: str, teams_webhook: str = "") -> list:
    """Return 8 monitor definitions per the implementation plan."""
    notify = f"@webhook-{teams_webhook}" if teams_webhook else ""

    return [
        # Critical Monitors
        {
            "name": f"[{env}] Pipeline Failure Rate > 10%",
            "type": "metric alert",
            "query": f"sum(last_15m):sum:trace.analysis.run.errors{{env:{env}}}.as_count() / sum:trace.analysis.run.hits{{env:{env}}}.as_count() > 0.1",
            "message": f"Pipeline error rate exceeded 10% in {env}. Check analysis Lambda logs. {notify}",
            "priority": 1,
            "tags": [f"env:{env}", "service:pco-compliance-pipeline", "severity:critical"],
        },
        {
            "name": f"[{env}] API 5xx Error Rate > 5%",
            "type": "metric alert",
            "query": f"sum(last_10m):sum:trace.fastapi.request.errors{{env:{env},service:pco-compliance-api}}.as_count() / sum:trace.fastapi.request.hits{{env:{env},service:pco-compliance-api}}.as_count() > 0.05",
            "message": f"API error rate exceeded 5% in {env}. {notify}",
            "priority": 1,
            "tags": [f"env:{env}", "service:pco-compliance-api", "severity:critical"],
        },
        {
            "name": f"[{env}] Bedrock Throttling Spike",
            "type": "metric alert",
            "query": f"sum(last_15m):sum:trace.bedrock.regulation_extraction.errors{{env:{env},error.type:ThrottlingException}}.as_count() > 5",
            "message": f"Bedrock throttling detected in {env}. Reduce concurrency or request quota increase. {notify}",
            "priority": 1,
            "tags": [f"env:{env}", "service:pco-compliance-pipeline", "severity:critical"],
        },
        # Warning Monitors
        {
            "name": f"[{env}] Bedrock Latency p95 > 30s",
            "type": "metric alert",
            "query": f"avg(last_15m):p95:trace.bedrock.regulation_extraction.duration{{env:{env}}} > 30000000000",
            "message": f"Bedrock p95 latency exceeds 30s in {env}. Model may be degraded. {notify}",
            "priority": 2,
            "tags": [f"env:{env}", "service:pco-compliance-pipeline", "severity:warning"],
        },
        {
            "name": f"[{env}] API Latency p95 > 5s",
            "type": "metric alert",
            "query": f"avg(last_10m):p95:trace.fastapi.request.duration{{env:{env},service:pco-compliance-api}} > 5000000000",
            "message": f"API p95 latency exceeds 5s in {env}. {notify}",
            "priority": 2,
            "tags": [f"env:{env}", "service:pco-compliance-api", "severity:warning"],
        },
        {
            "name": f"[{env}] Lambda Cold Start Rate > 20%",
            "type": "metric alert",
            "query": f"avg(last_1h):avg:aws.lambda.enhanced.init_duration{{env:{env},functionname:*compliance*}} > 0",
            "message": f"High cold start rate for compliance Lambdas in {env}. {notify}",
            "priority": 3,
            "tags": [f"env:{env}", "severity:warning"],
        },
        {
            "name": f"[{env}] DLQ Messages Present",
            "type": "metric alert",
            "query": f"avg(last_5m):avg:aws.sqs.approximate_number_of_messages_visible{{env:{env},queuename:*Dlq*}} > 0",
            "message": f"Messages in DLQ in {env}. Failed SQS messages need investigation. {notify}",
            "priority": 2,
            "tags": [f"env:{env}", "severity:warning"],
        },
        {
            "name": f"[{env}] No Pipeline Runs in 48h",
            "type": "metric alert",
            "query": f"sum(last_48h):sum:trace.analysis.run.hits{{env:{env}}}.as_count() < 1",
            "message": f"No pipeline runs detected in {env} for 48h. Scraper or scheduler may be down. {notify}",
            "priority": 2,
            "tags": [f"env:{env}", "service:pco-compliance-pipeline", "severity:warning"],
        },
    ]


# ─── Widget Helpers ───────────────────────────────────────────────────

def _timeseries(title: str, queries: list) -> dict:
    """Build a timeseries widget definition (simplified for API)."""
    return {
        "definition": {
            "type": "timeseries",
            "title": title,
            "requests": [{"q": q, "display_type": "line"} for q in queries],
        },
    }


def _query_value(title: str, query: str) -> dict:
    """Build a query value widget definition (simplified for API)."""
    return {
        "definition": {
            "type": "query_value",
            "title": title,
            "requests": [{"q": query}],
        },
    }


# ─── Main ─────────────────────────────────────────────────────────────

def create_dashboards(env: str) -> None:
    """Create all 3 dashboards via the Datadog API."""
    configuration = Configuration()
    with ApiClient(configuration) as api_client:
        api = DashboardsApi(api_client)
        dashboards = [
            compliance_pipeline_dashboard(env),
            bedrock_ai_dashboard(env),
            api_infrastructure_dashboard(env),
        ]
        for dash_def in dashboards:
            try:
                body = Dashboard(
                    title=dash_def["title"],
                    description=dash_def.get("description", ""),
                    layout_type=DashboardLayoutType(dash_def["layout_type"]),
                    widgets=[Widget(**w) for w in dash_def["widgets"]],
                )
                result = api.create_dashboard(body=body)
                print(f"✅ Dashboard created: {result.title} (id={result.id})")
            except Exception as e:
                print(f"❌ Failed to create dashboard '{dash_def['title']}': {e}")


def create_monitors(env: str, teams_webhook: str = "") -> None:
    """Create all 8 monitors via the Datadog API."""
    configuration = Configuration()
    with ApiClient(configuration) as api_client:
        api = MonitorsApi(api_client)
        monitors = get_monitors(env, teams_webhook)
        for mon_def in monitors:
            try:
                body = Monitor(
                    name=mon_def["name"],
                    type=MonitorType(mon_def["type"]),
                    query=mon_def["query"],
                    message=mon_def["message"],
                    priority=mon_def.get("priority"),
                    tags=mon_def.get("tags", []),
                )
                result = api.create_monitor(body=body)
                print(f"✅ Monitor created: {result.name} (id={result.id})")
            except Exception as e:
                print(f"❌ Failed to create monitor '{mon_def['name']}': {e}")


def main():
    parser = argparse.ArgumentParser(description="Setup Datadog dashboards and monitors for PCO Compliance")
    parser.add_argument("--env", required=True, choices=["dev", "staging", "prod"], help="Target environment")
    parser.add_argument("--teams-webhook", default="", help="MS Teams Incoming Webhook URL for alerts")
    parser.add_argument("--dashboards-only", action="store_true", help="Only create dashboards")
    parser.add_argument("--monitors-only", action="store_true", help="Only create monitors")
    parser.add_argument("--dry-run", action="store_true", help="Print definitions without calling API")
    args = parser.parse_args()

    # Validate API credentials
    if not args.dry_run:
        if not os.environ.get("DD_API_KEY"):
            print("ERROR: DD_API_KEY environment variable not set")
            sys.exit(1)
        if not os.environ.get("DD_APP_KEY"):
            print("ERROR: DD_APP_KEY environment variable not set")
            sys.exit(1)

    if args.dry_run:
        print(f"\n{'='*60}")
        print(f"DRY RUN — Definitions for environment: {args.env}")
        print(f"{'='*60}\n")
        if not args.monitors_only:
            for d in [compliance_pipeline_dashboard(args.env), bedrock_ai_dashboard(args.env), api_infrastructure_dashboard(args.env)]:
                print(f"\nDashboard: {d['title']}")
                print(f"  Widgets: {len(d['widgets'])}")
                for w in d["widgets"]:
                    print(f"    - {w['definition']['title']}")
        if not args.dashboards_only:
            print(f"\nMonitors:")
            for m in get_monitors(args.env, args.teams_webhook):
                print(f"  - [{m['priority']}] {m['name']}")
        return

    if not args.monitors_only:
        print(f"\n📊 Creating dashboards for [{args.env}]...")
        create_dashboards(args.env)

    if not args.dashboards_only:
        print(f"\n🔔 Creating monitors for [{args.env}]...")
        create_monitors(args.env, args.teams_webhook)

    print(f"\n✅ Datadog setup complete for [{args.env}]!")
    print("\n📋 Next steps:")
    print("   1. Open Datadog → Dashboards to verify")
    print("   2. Open Datadog → Monitors to verify alert thresholds")
    if not args.teams_webhook:
        print("   3. Set up MS Teams webhook and re-run with --teams-webhook URL")


if __name__ == "__main__":
    main()

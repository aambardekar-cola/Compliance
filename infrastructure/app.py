#!/usr/bin/env python3
"""CDK App entry point for PaceCareOnline Compliance Intelligence Platform.

Usage:
    cdk synth -c env=dev
    cdk deploy --all -c env=staging
    cdk deploy --all -c env=prod --require-approval never
"""
import os
import sys
import aws_cdk as cdk

from stacks.data_stack import DataStack
from stacks.api_stack import ApiStack
from stacks.pipeline_stack import PipelineStack
from stacks.notification_stack import NotificationStack
from stacks.frontend_stack import FrontendStack

app = cdk.App()

# ---- Resolve environment ----
deploy_env = app.node.try_get_context("env") or os.environ.get("DEPLOY_ENV", "dev")
environments = app.node.try_get_context("environments") or {}
env_config = environments.get(deploy_env)

if not env_config:
    print(f"ERROR: Unknown environment '{deploy_env}'. Valid: {list(environments.keys())}")
    sys.exit(1)

app_name = env_config["app_name"]
log_level = env_config.get("log_level", "INFO")
aurora_min = env_config.get("aurora_min_capacity", 0.5)
aurora_max = env_config.get("aurora_max_capacity", 8)
nat_gateways = env_config.get("nat_gateways", 1)

aws_env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", app.node.try_get_context("aws_region") or "us-east-1"),
)

print(f"Synthesizing for environment: {deploy_env} ({app_name})")

# --- Data Layer ---
data_stack = DataStack(
    app,
    f"{app_name}-data",
    env=aws_env,
    aurora_min_capacity=aurora_min,
    aurora_max_capacity=aurora_max,
    nat_gateways=nat_gateways,
    deploy_env=deploy_env,
    description=f"[{deploy_env}] Aurora Serverless v2 (PostgreSQL) and S3 buckets",
)

# --- API Layer ---
api_stack = ApiStack(
    app,
    f"{app_name}-api",
    env=aws_env,
    vpc=data_stack.vpc,
    db_secret=data_stack.db_secret,
    db_proxy=data_stack.db_proxy,
    documents_bucket=data_stack.documents_bucket,
    lambda_security_group=data_stack.lambda_security_group,
    deploy_env=deploy_env,
    log_level=log_level,
    descope_project_id=env_config.get("descope_project_id", ""),
    dd_api_key_secret=data_stack.dd_api_key_secret,
    description=f"[{deploy_env}] API Gateway + FastAPI Lambda",
)
api_stack.add_dependency(data_stack)

# --- Pipeline Layer ---
pipeline_stack = PipelineStack(
    app,
    f"{app_name}-pipeline",
    env=aws_env,
    vpc=data_stack.vpc,
    db_secret=data_stack.db_secret,
    db_proxy=data_stack.db_proxy,
    documents_bucket=data_stack.documents_bucket,
    lambda_security_group=data_stack.lambda_security_group,
    deploy_env=deploy_env,
    dd_api_key_secret=data_stack.dd_api_key_secret,
    description=f"[{deploy_env}] Regulatory ingestion and analysis pipeline",
)
pipeline_stack.add_dependency(data_stack)

# Wire the analysis queue URL into the API Lambda so the admin
# trigger-analysis endpoint can re-queue unprocessed content.
api_stack.api_lambda.add_environment(
    "ANALYSIS_QUEUE_URL", pipeline_stack.analysis_queue.queue_url
)
pipeline_stack.analysis_queue.grant_send_messages(api_stack.api_lambda)

# --- Notification Layer ---
notification_stack = NotificationStack(
    app,
    f"{app_name}-notifications",
    env=aws_env,
    vpc=data_stack.vpc,
    db_secret=data_stack.db_secret,
    db_proxy=data_stack.db_proxy,
    lambda_security_group=data_stack.lambda_security_group,
    deploy_env=deploy_env,
    dd_api_key_secret=data_stack.dd_api_key_secret,
    description=f"[{deploy_env}] SES email delivery and communication Lambdas",
)
notification_stack.add_dependency(data_stack)

# --- Frontend Layer ---
frontend_stack = FrontendStack(
    app,
    f"{app_name}-frontend",
    env=aws_env,
    api_url=api_stack.api_url,
    description=f"[{deploy_env}] CloudFront + S3 static hosting for React SPA",
)
frontend_stack.add_dependency(api_stack)

# ---- Global Tags ----
cdk.Tags.of(app).add("product", "pco-compliance")
cdk.Tags.of(app).add("environment", deploy_env)

app.synth()

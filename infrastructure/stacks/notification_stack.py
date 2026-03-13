"""Notification Stack: SES email delivery and executive reporting Lambdas."""
import aws_cdk as cdk
from aws_cdk import (
    aws_lambda as lambda_,
    aws_ec2 as ec2,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    aws_rds as rds,
    Duration,
)
from constructs import Construct


class NotificationStack(cdk.Stack):
    """SES email delivery and executive reporting Lambdas."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        db_secret: secretsmanager.ISecret,
        db_proxy: rds.IDatabaseProxy,
        lambda_security_group: ec2.ISecurityGroup,
        deploy_env: str = "dev",
        dd_api_key_secret: secretsmanager.ISecret = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---- Lambda Security Group ----
        lambda_sg = ec2.SecurityGroup(
            self,
            "NotificationLambdaSg",
            vpc=vpc,
            description="Security group for notification Lambdas",
            allow_all_outbound=True,
        )

        # ---- Lambda Layer for Python dependencies ----
        deps_layer = lambda_.LayerVersion(
            self,
            "NotificationDepsLayer",
            code=lambda_.Code.from_asset("../backend/layer"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[lambda_.Architecture.ARM_64],
            description="Python dependencies for notification Lambdas",
        )

        # ---- Datadog APM Layers ----
        notif_layers = [deps_layer]
        dd_env = {}
        if dd_api_key_secret:
            dd_extension_layer = lambda_.LayerVersion.from_layer_version_arn(
                self, "DatadogExtension",
                f"arn:aws:lambda:{cdk.Stack.of(self).region}:464622532012:layer:Datadog-Extension-ARM:93",
            )
            dd_python_layer = lambda_.LayerVersion.from_layer_version_arn(
                self, "DatadogPython",
                f"arn:aws:lambda:{cdk.Stack.of(self).region}:464622532012:layer:Datadog-Python312-ARM:123",
            )
            notif_layers.extend([dd_extension_layer, dd_python_layer])
            dd_env = {
                "DD_API_KEY_SECRET_ARN": dd_api_key_secret.secret_arn,
                "DD_SITE": "datadoghq.com",
                "DD_ENV": deploy_env,
                "DD_SERVICE": "pco-compliance-notifications",
                "DD_TRACE_ENABLED": "true",
                "DD_SERVERLESS_LOGS_ENABLED": "true",
                "DD_CAPTURE_LAMBDA_PAYLOAD": "false",
                "DD_TRACE_SAMPLE_RATE": "0.1" if deploy_env in ("dev", "staging") else "1.0",
            }

        # ---- Reporting Lambda (Weekly exec summaries) ----
        self.reporting_lambda = lambda_.Function(
            self,
            "ReportingHandler",
            code=lambda_.Code.from_asset(
                "../backend",
                exclude=[
                    "venv", "venv/**", "layer", "layer/**",
                    "__pycache__", "**/__pycache__/**",
                    "*.pyc", "tests", "tests/**",
                    "local_test.db", "failed_logs.txt",
                ],
            ),
            handler="reporting.handler.handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            memory_size=512,
            timeout=Duration.minutes(5),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_groups=[lambda_sg, lambda_security_group],
            layers=notif_layers,
            environment={
                "DB_SECRET_ARN": db_secret.secret_arn,
                "DB_PROXY_ENDPOINT": db_proxy.endpoint,
                "APP_ENV": deploy_env,
                "SES_FROM_EMAIL": "compliance@collabrios.com",
                "LOG_LEVEL": "INFO",
                **dd_env,
            },
        )

        db_secret.grant_read(self.reporting_lambda)
        if dd_api_key_secret:
            dd_api_key_secret.grant_read(self.reporting_lambda)

        self.reporting_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=["*"],
            )
        )

        self.reporting_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel"],
                resources=["arn:aws:bedrock:*::foundation-model/*"],
            )
        )

        # ---- EventBridge weekly cron → triggers reporting Lambda ----
        self.weekly_report_rule = events.Rule(
            self,
            "WeeklyReportCron",
            schedule=events.Schedule.cron(
                minute="0",
                hour="13",       # 8 AM EST = 13:00 UTC
                week_day="MON",
            ),
            description="Trigger weekly executive report generation every Monday at 8 AM EST",
        )
        self.weekly_report_rule.add_target(
            targets.LambdaFunction(
                self.reporting_lambda,
                event=events.RuleTargetInput.from_object({
                    "send_email": True,
                    "source": "scheduled",
                }),
            )
        )

        # ---- CDK Outputs ----
        cdk.CfnOutput(
            self, "ReportingLambdaArn",
            value=self.reporting_lambda.function_arn,
            description="Reporting Lambda ARN",
        )

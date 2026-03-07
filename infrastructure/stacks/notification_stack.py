"""Notification Stack: SES email delivery and communication Lambdas."""
import aws_cdk as cdk
from aws_cdk import (
    aws_lambda as lambda_,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    aws_rds as rds,
    Duration,
)
from constructs import Construct


class NotificationStack(cdk.Stack):
    """SES email delivery and communication generation Lambdas."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        db_secret: secretsmanager.ISecret,
        db_proxy: rds.IDatabaseProxy,
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

        # ---- Communication Generator Lambda ----
        self.comm_lambda = lambda_.Function(
            self,
            "CommunicationHandler",
            code=lambda_.Code.from_asset("../backend"),
            handler="communications.handler.handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            memory_size=512,
            timeout=Duration.minutes(5),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_groups=[lambda_sg],
            layers=[deps_layer],
            environment={
                "DB_SECRET_ARN": db_secret.secret_arn,
                "DB_PROXY_ENDPOINT": db_proxy.endpoint,
                "SES_FROM_EMAIL": "compliance@collabrios.com",
                "LOG_LEVEL": "INFO",
            },
        )

        # Grant permissions
        db_secret.grant_read(self.comm_lambda)

        # SES send permissions
        self.comm_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ses:SendEmail",
                    "ses:SendRawEmail",
                    "ses:SendTemplatedEmail",
                ],
                resources=["*"],
            )
        )

        # Bedrock permissions for communication drafting
        self.comm_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel"],
                resources=["arn:aws:bedrock:*::foundation-model/*"],
            )
        )

        # ---- Reporting Lambda (Weekly exec summaries) ----
        self.reporting_lambda = lambda_.Function(
            self,
            "ReportingHandler",
            code=lambda_.Code.from_asset("../backend"),
            handler="reporting.handler.handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            memory_size=512,
            timeout=Duration.minutes(5),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_groups=[lambda_sg],
            layers=[deps_layer],
            environment={
                "DB_SECRET_ARN": db_secret.secret_arn,
                "DB_PROXY_ENDPOINT": db_proxy.endpoint,
                "SES_FROM_EMAIL": "compliance@collabrios.com",
                "LOG_LEVEL": "INFO",
            },
        )

        db_secret.grant_read(self.reporting_lambda)

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

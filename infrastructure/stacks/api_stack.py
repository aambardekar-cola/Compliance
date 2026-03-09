"""API Stack: API Gateway + FastAPI Lambda with Descope JWT authorizer."""
import aws_cdk as cdk
from aws_cdk import (
    aws_apigateway as apigw,
    aws_lambda as lambda_,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
    aws_rds as rds,
    Duration,
)
from constructs import Construct


class ApiStack(cdk.Stack):
    """API Gateway with FastAPI Lambda and Descope JWT authorization."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        db_secret: secretsmanager.ISecret,
        db_proxy: rds.IDatabaseProxy,
        documents_bucket: s3.IBucket,
        lambda_security_group: ec2.ISecurityGroup,
        deploy_env: str = "dev",
        log_level: str = "INFO",
        descope_project_id: str = "",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---- Lambda Security Group ----
        lambda_sg = ec2.SecurityGroup(
            self,
            "ApiLambdaSg",
            vpc=vpc,
            description="Security group for API Lambda",
            allow_all_outbound=True,
        )

        # ---- Lambda Layer for Python dependencies ----
        deps_layer = lambda_.LayerVersion(
            self,
            "PythonDepsLayer",
            code=lambda_.Code.from_asset("../backend/layer"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[lambda_.Architecture.ARM_64],
            description="Python dependencies for backend Lambdas",
        )

        # ---- FastAPI Lambda ----
        self.api_lambda = lambda_.Function(
            self,
            "ApiHandler",
            code=lambda_.Code.from_asset("../backend"),
            handler="api.main.handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            memory_size=512,
            timeout=Duration.seconds(30),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_groups=[lambda_sg, lambda_security_group],
            layers=[deps_layer],
            environment={
                "DB_SECRET_ARN": db_secret.secret_arn,
                "DB_PROXY_ENDPOINT": db_proxy.endpoint,
                "DOCUMENTS_BUCKET": documents_bucket.bucket_name,
                "APP_ENV": deploy_env,
                "LOG_LEVEL": log_level,
                "DESCOPE_PROJECT_ID": descope_project_id,
            },
        )

        # Grant permissions
        db_secret.grant_read(self.api_lambda)
        documents_bucket.grant_read_write(self.api_lambda)

        # Bedrock permissions
        self.api_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=["arn:aws:bedrock:*::foundation-model/*"],
            )
        )

        # ---- API Gateway ----
        self.api = apigw.LambdaRestApi(
            self,
            "ComplianceApi",
            handler=self.api_lambda,
            proxy=True,
            deploy_options=apigw.StageOptions(
                stage_name="api",
                throttling_rate_limit=100,
                throttling_burst_limit=200,
                logging_level=apigw.MethodLoggingLevel.INFO,
            ),
            # Removing default_cors_preflight_options from API Gateway.
            # CORS is handled entirely by FastAPI's CORSMiddleware.
        )

        # Add health check endpoint (no auth)
        health = self.api.root.add_resource("health")
        health.add_method(
            "GET",
            apigw.LambdaIntegration(self.api_lambda),
        )

        # ---- Force New Deployment ----
        # API Gateway is caching a ghost OPTIONS method from a previous deployment.
        # Adding this dummy resource alters the CDK Deployment hash, explicitly forcing
        # a new AWS::ApiGateway::Deployment to be generated and bound to the live Stage,
        # which will wipe out the rogue OPTIONS mock integrations.
        self.api.root.add_resource("force_deploy_1").add_method(
            "GET",
            apigw.LambdaIntegration(self.api_lambda)
        )

        self.api_url = self.api.url

        # ---- Outputs ----
        cdk.CfnOutput(self, "ApiUrl", value=self.api.url)
        cdk.CfnOutput(
            self, "ApiLambdaArn", value=self.api_lambda.function_arn
        )


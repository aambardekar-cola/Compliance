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
            security_groups=[lambda_sg],
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

        # ---- Descope JWT Authorizer Lambda ----
        authorizer_lambda = lambda_.Function(
            self,
            "AuthorizerHandler",
            code=lambda_.Code.from_asset("../backend"),
            handler="api.middleware.authorizer.handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            memory_size=256,
            timeout=Duration.seconds(10),
            layers=[deps_layer],
            environment={
                "LOG_LEVEL": log_level,
                "DESCOPE_PROJECT_ID": descope_project_id,
            },
        )

        # ---- API Gateway ----
        authorizer = apigw.TokenAuthorizer(
            self,
            "DescopeAuthorizer",
            handler=authorizer_lambda,
            results_cache_ttl=Duration.minutes(5),
            identity_source="method.request.header.Authorization",
        )

        self.api = apigw.LambdaRestApi(
            self,
            "ComplianceApi",
            handler=self.api_lambda,
            proxy=True,
            default_method_options=apigw.MethodOptions(
                authorizer=authorizer,
                authorization_type=apigw.AuthorizationType.CUSTOM,
            ),
            deploy_options=apigw.StageOptions(
                stage_name="api",
                throttling_rate_limit=100,
                throttling_burst_limit=200,
                logging_level=apigw.MethodLoggingLevel.INFO,
            ),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Tenant-Id",
                ],
            ),
        )

        # Add health check endpoint (no auth)
        health = self.api.root.add_resource("health")
        health.add_method(
            "GET",
            apigw.LambdaIntegration(self.api_lambda),
            authorization_type=apigw.AuthorizationType.NONE,
        )

        self.api_url = self.api.url

        # ---- Outputs ----
        cdk.CfnOutput(self, "ApiUrl", value=self.api.url)
        cdk.CfnOutput(
            self, "ApiLambdaArn", value=self.api_lambda.function_arn
        )

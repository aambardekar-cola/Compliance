"""Data Stack: Aurora Serverless v2 (PostgreSQL) and S3 buckets."""
import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    aws_lambda as lambda_,
    aws_rds as rds,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
    RemovalPolicy,
    Duration,
)
from constructs import Construct


class DataStack(cdk.Stack):
    """Provisions the data layer: Aurora Serverless v2 PostgreSQL and S3 buckets."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        aurora_min_capacity: float = 0.5,
        aurora_max_capacity: float = 8,
        nat_gateways: int = 1,
        deploy_env: str = "dev",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---- VPC ----
        self.vpc = ec2.Vpc(
            self,
            "ComplianceVpc",
            max_azs=2,
            nat_gateways=nat_gateways,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        # ---- Security Groups ----
        self.db_security_group = ec2.SecurityGroup(
            self,
            "DbSecurityGroup",
            vpc=self.vpc,
            description="Security group for Aurora Serverless v2",
            allow_all_outbound=False,
        )

        self.lambda_security_group = ec2.SecurityGroup(
            self,
            "LambdaSecurityGroup",
            vpc=self.vpc,
            description="Security group for Lambda functions",
            allow_all_outbound=True,
        )

        # Allow Lambda → Aurora on PostgreSQL port
        self.db_security_group.add_ingress_rule(
            peer=self.lambda_security_group,
            connection=ec2.Port.tcp(5432),
            description="Allow Lambda to connect to Aurora PostgreSQL",
        )

        # ---- Aurora Serverless v2 (PostgreSQL) ----
        self.db_secret = secretsmanager.Secret(
            self,
            "DbSecret",
            secret_name="pco-compliance/db-credentials",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username": "compliance_admin"}',
                generate_string_key="password",
                exclude_punctuation=True,
                password_length=32,
            ),
        )

        self.db_cluster = rds.DatabaseCluster(
            self,
            "ComplianceDb",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_16_4,
            ),
            credentials=rds.Credentials.from_secret(self.db_secret),
            default_database_name="compliance_db",
            serverless_v2_min_capacity=aurora_min_capacity,
            serverless_v2_max_capacity=aurora_max_capacity,
            writer=rds.ClusterInstance.serverless_v2(
                "Writer",
                auto_minor_version_upgrade=True,
            ),
            readers=[
                rds.ClusterInstance.serverless_v2(
                    "Reader",
                    scale_with_writer=True,
                ),
            ],
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
            ),
            security_groups=[self.db_security_group],
            storage_encrypted=True,
            backup=rds.BackupProps(retention=Duration.days(7)),
            removal_policy=RemovalPolicy.SNAPSHOT,
        )

        # ---- RDS Proxy (for Lambda connection pooling) ----
        self.db_proxy = self.db_cluster.add_proxy(
            "DbProxy",
            secrets=[self.db_secret],
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_groups=[self.db_security_group],
            require_tls=True,
            debug_logging=False,
        )

        # ---- S3 Buckets ----
        self.documents_bucket = s3.Bucket(
            self,
            "DocumentsBucket",
            bucket_name=None,  # Auto-generated unique name
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            versioned=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ArchiveOldDocuments",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(90),
                        ),
                    ],
                ),
            ],
        )

        self.reports_bucket = s3.Bucket(
            self,
            "ReportsBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            versioned=True,
        )

        # ---- Migration Runner Lambda ----
        # Lambda Layer for Python deps (shared with other stacks)
        deps_layer = lambda_.LayerVersion(
            self,
            "MigrationDepsLayer",
            code=lambda_.Code.from_asset("../backend/layer"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[lambda_.Architecture.ARM_64],
            description="Python dependencies for migration Lambda",
        )

        migration_lambda = lambda_.Function(
            self,
            "MigrationRunner",
            code=lambda_.Code.from_asset(
                "../backend",
                exclude=[
                    "venv", "venv/**", "layer", "layer/**",
                    "__pycache__", "**/__pycache__/**",
                    "*.pyc", "tests", "tests/**",
                    "local_test.db", "failed_logs.txt",
                ],
            ),
            handler="migrations.runner.handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            memory_size=512,
            timeout=Duration.minutes(5),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_groups=[self.lambda_security_group],
            layers=[deps_layer],
            environment={
                "DB_SECRET_ARN": self.db_secret.secret_arn,
                "DB_PROXY_ENDPOINT": self.db_proxy.endpoint,
                "APP_ENV": deploy_env,
            },
        )

        self.db_secret.grant_read(migration_lambda)

        # Allow migration Lambda to connect to the DB via the proxy
        self.db_security_group.add_ingress_rule(
            peer=self.lambda_security_group,
            connection=ec2.Port.tcp(5432),
            description="Allow migration Lambda to connect to Aurora via RDS Proxy",
        )

        # Export migration Lambda ARN for manual invocation
        self.migration_lambda_arn = migration_lambda.function_arn

        # ---- Outputs ----
        cdk.CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
        cdk.CfnOutput(
            self, "DbClusterEndpoint", value=self.db_cluster.cluster_endpoint.hostname
        )
        cdk.CfnOutput(
            self, "DbProxyEndpoint", value=self.db_proxy.endpoint
        )
        cdk.CfnOutput(
            self, "DocumentsBucketName", value=self.documents_bucket.bucket_name
        )
        cdk.CfnOutput(
            self, "ReportsBucketName", value=self.reports_bucket.bucket_name
        )
        cdk.CfnOutput(
            self, "MigrationLambdaArn", value=migration_lambda.function_arn
        )

        # ---- Datadog API Key Secret ----
        # Stores the DD API key for Lambda extension telemetry forwarding.
        # After first deploy, update the secret value in AWS Console:
        #   aws secretsmanager put-secret-value \
        #     --secret-id pco-compliance/datadog-api-key \
        #     --secret-string '{"api_key":"<YOUR_DD_API_KEY>"}'
        self.dd_api_key_secret = secretsmanager.Secret(
            self,
            "DatadogApiKeySecret",
            secret_name=f"pco-compliance/datadog-api-key-{deploy_env}",
            description="Datadog API key for Lambda APM instrumentation",
        )

        cdk.CfnOutput(
            self, "DatadogApiKeySecretArn", value=self.dd_api_key_secret.secret_arn
        )

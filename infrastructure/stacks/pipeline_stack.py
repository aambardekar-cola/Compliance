"""Pipeline Stack: Regulatory ingestion and analysis pipeline."""
import aws_cdk as cdk
from aws_cdk import (
    aws_lambda as lambda_,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_sqs as sqs,
    aws_s3 as s3,
    aws_events as events,
    aws_events_targets as events_targets,
    aws_lambda_event_sources as lambda_event_sources,
    aws_secretsmanager as secretsmanager,
    aws_rds as rds,
    aws_bedrock as bedrock,
    Duration,
)
from constructs import Construct


class PipelineStack(cdk.Stack):
    """Regulatory ingestion pipeline with EventBridge schedules and SQS queues."""

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
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---- Lambda Security Group ----
        lambda_sg = ec2.SecurityGroup(
            self,
            "PipelineLambdaSg",
            vpc=vpc,
            description="Security group for pipeline Lambdas",
            allow_all_outbound=True,
        )

        # ---- Lambda Layer for Python dependencies ----
        deps_layer = lambda_.LayerVersion(
            self,
            "PipelineDepsLayer",
            code=lambda_.Code.from_asset("../backend/layer"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[lambda_.Architecture.ARM_64],
            description="Python dependencies for pipeline Lambdas",
        )

        # ---- SQS Queues ----
        # Dead letter queue for failed processing
        dlq = sqs.Queue(
            self,
            "PipelineDlq",
            retention_period=Duration.days(14),
            visibility_timeout=Duration.minutes(15),
        )

        # Queue for gap analysis (triggered after regulation ingestion)
        self.analysis_queue = sqs.Queue(
            self,
            "AnalysisQueue",
            visibility_timeout=Duration.minutes(15),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=dlq,
            ),
        )

        # Queue for communication generation
        self.communication_queue = sqs.Queue(
            self,
            "CommunicationQueue",
            visibility_timeout=Duration.minutes(10),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=dlq,
            ),
        )

        # ---- Bedrock Application Inference Profiles (for cost allocation tagging) ----
        haiku_model_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
        sonnet_model_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

        haiku_profile = bedrock.CfnApplicationInferenceProfile(
            self,
            "HaikuInferenceProfile",
            inference_profile_name=f"pco-{deploy_env}-haiku-4-5",
            model_source=bedrock.CfnApplicationInferenceProfile.InferenceProfileModelSourceProperty(
                copy_from=f"arn:aws:bedrock:us-east-2::inference-profile/{haiku_model_id}",
            ),
            description=f"Claude Haiku 4.5 PCO compliance filtering-{deploy_env}",
            tags=[
                cdk.CfnTag(key="product", value="pco-compliance"),
                cdk.CfnTag(key="environment", value=deploy_env),
                cdk.CfnTag(key="model", value="claude-haiku-4.5"),
                cdk.CfnTag(key="purpose", value="regulation-filtering"),
            ],
        )

        sonnet_profile = bedrock.CfnApplicationInferenceProfile(
            self,
            "SonnetInferenceProfile",
            inference_profile_name=f"pco-{deploy_env}-sonnet-4-5",
            model_source=bedrock.CfnApplicationInferenceProfile.InferenceProfileModelSourceProperty(
                copy_from=f"arn:aws:bedrock:us-east-2::inference-profile/{sonnet_model_id}",
            ),
            description=f"Claude Sonnet 4.5 PCO compliance analysis-{deploy_env}",
            tags=[
                cdk.CfnTag(key="product", value="pco-compliance"),
                cdk.CfnTag(key="environment", value=deploy_env),
                cdk.CfnTag(key="model", value="claude-sonnet-4.5"),
                cdk.CfnTag(key="purpose", value="regulation-analysis"),
            ],
        )

        # Shared environment variables
        common_env = {
            "DB_SECRET_ARN": db_secret.secret_arn,
            "DB_PROXY_ENDPOINT": db_proxy.endpoint,
            "DOCUMENTS_BUCKET": documents_bucket.bucket_name,
            "ANALYSIS_QUEUE_URL": self.analysis_queue.queue_url,
            "COMMUNICATION_QUEUE_URL": self.communication_queue.queue_url,
            "APP_ENV": deploy_env,
            "LOG_LEVEL": "INFO",
            # Bedrock: use Application Inference Profile ARNs for cost allocation tagging
            "BEDROCK_HAIKU_MODEL_ID": haiku_profile.attr_inference_profile_arn,
            "BEDROCK_SONNET_MODEL_ID": sonnet_profile.attr_inference_profile_arn,
            "MAX_CHUNKS_PER_RUN": "5",  # Process 5 chunks per invocation; trigger again to continue
        }

        # ---- Ingestion Lambda ----
        self.ingestion_lambda = lambda_.Function(
            self,
            "IngestionHandler",
            code=lambda_.Code.from_asset(
                "../backend",
                exclude=[
                    "venv", "venv/**", "layer", "layer/**",
                    "__pycache__", "**/__pycache__/**",
                    "*.pyc", "tests", "tests/**",
                    "local_test.db", "failed_logs.txt",
                ],
            ),
            handler="ingestion.handler.handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            memory_size=1024,
            timeout=Duration.minutes(10),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_groups=[lambda_sg, lambda_security_group],
            layers=[deps_layer],
            environment=common_env,
        )

        # Grant permissions
        db_secret.grant_read(self.ingestion_lambda)
        documents_bucket.grant_read_write(self.ingestion_lambda)
        self.analysis_queue.grant_send_messages(self.ingestion_lambda)

        # Bedrock access for relevance scoring (via inference profiles + foundation models)
        self.ingestion_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel"],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/*",
                    "arn:aws:bedrock:*:*:inference-profile/*",
                    "arn:aws:bedrock:*:*:application-inference-profile/*",
                ],
            )
        )

        # ---- Analysis Lambda ----
        self.analysis_lambda = lambda_.Function(
            self,
            "AnalysisHandler",
            code=lambda_.Code.from_asset(
                "../backend",
                exclude=[
                    "venv", "venv/**", "layer", "layer/**",
                    "__pycache__", "**/__pycache__/**",
                    "*.pyc", "tests", "tests/**",
                    "local_test.db", "failed_logs.txt",
                ],
            ),
            handler="analysis.handler.handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            memory_size=1024,
            timeout=Duration.minutes(15),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_groups=[lambda_sg, lambda_security_group],
            layers=[deps_layer],
            environment=common_env,
        )

        # SQS trigger
        self.analysis_lambda.add_event_source(
            lambda_event_sources.SqsEventSource(
                self.analysis_queue,
                batch_size=1,
            )
        )

        # Grant permissions
        db_secret.grant_read(self.analysis_lambda)
        documents_bucket.grant_read_write(self.analysis_lambda)
        self.communication_queue.grant_send_messages(self.analysis_lambda)

        self.analysis_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel"],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/*",
                    "arn:aws:bedrock:*:*:inference-profile/*",
                    "arn:aws:bedrock:*:*:application-inference-profile/*",
                ],
            )
        )

        # AWS Marketplace permissions for auto-enabling newer Bedrock models
        # (Haiku 4.5, Sonnet 4.5 are served via Marketplace)
        self.analysis_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "aws-marketplace:Subscribe",
                    "aws-marketplace:ViewSubscriptions",
                ],
                resources=["*"],
            )
        )

        # ---- Scraper Lambda ----
        self.scraper_lambda = lambda_.Function(
            self,
            "ScraperHandler",
            code=lambda_.Code.from_asset(
                "../backend",
                exclude=[
                    "venv", "venv/**", "layer", "layer/**",
                    "__pycache__", "**/__pycache__/**",
                    "*.pyc", "tests", "tests/**",
                    "local_test.db", "failed_logs.txt",
                ],
            ),
            handler="lambdas.scraper.main.handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            memory_size=1024,
            timeout=Duration.minutes(10),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_groups=[lambda_sg, lambda_security_group],
            layers=[deps_layer],
            environment=common_env,
        )

        db_secret.grant_read(self.scraper_lambda)
        documents_bucket.grant_read_write(self.scraper_lambda)
        self.analysis_queue.grant_send_messages(self.scraper_lambda)

        # ---- EventBridge: Daily Scraper Schedule ----
        events.Rule(
            self,
            "DailyScraperRule",
            schedule=events.Schedule.cron(
                minute="0",
                hour="2",
                month="*",
                week_day="*",
                year="*",
            ),
            targets=[events_targets.LambdaFunction(self.scraper_lambda)],
            description="Trigger URL scraping daily at 2 AM UTC",
        )

        # ---- EventBridge: Daily Ingestion Schedule ----
        events.Rule(
            self,
            "DailyIngestionRule",
            schedule=events.Schedule.cron(
                minute="0",
                hour="6",
                month="*",
                week_day="*",
                year="*",
            ),
            targets=[events_targets.LambdaFunction(self.ingestion_lambda)],
            description="Trigger regulatory ingestion daily at 6 AM UTC",
        )

        # ---- Outputs ----
        cdk.CfnOutput(
            self, "AnalysisQueueUrl", value=self.analysis_queue.queue_url
        )
        cdk.CfnOutput(
            self,
            "CommunicationQueueUrl",
            value=self.communication_queue.queue_url,
        )

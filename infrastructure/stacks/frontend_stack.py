"""Frontend Stack: CloudFront + S3 for React SPA hosting."""
import aws_cdk as cdk
from aws_cdk import (
    aws_s3 as s3,
    aws_s3_deployment as s3_deploy,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    RemovalPolicy,
)
from constructs import Construct


class FrontendStack(cdk.Stack):
    """CloudFront distribution with S3 origin for the React SPA."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        api_url: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---- S3 Bucket for static assets ----
        self.site_bucket = s3.Bucket(
            self,
            "SiteBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # ---- CloudFront Distribution ----
        self.distribution = cloudfront.Distribution(
            self,
            "SiteDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    self.site_bucket
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
            ),
            default_root_object="index.html",
            error_responses=[
                # SPA: redirect 403/404 to index.html for client-side routing
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=cdk.Duration.minutes(5),
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=cdk.Duration.minutes(5),
                ),
            ],
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
        )

        # ---- Deploy frontend build to S3 ----
        s3_deploy.BucketDeployment(
            self,
            "DeploySite",
            sources=[s3_deploy.Source.asset("../frontend/dist")],
            destination_bucket=self.site_bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],
        )

        # ---- Outputs ----
        cdk.CfnOutput(
            self,
            "DistributionDomainName",
            value=self.distribution.distribution_domain_name,
        )
        cdk.CfnOutput(
            self, "SiteBucketName", value=self.site_bucket.bucket_name
        )
        cdk.CfnOutput(self, "ApiUrl", value=api_url)

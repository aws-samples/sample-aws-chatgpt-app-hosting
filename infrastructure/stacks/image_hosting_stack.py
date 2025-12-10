from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    RemovalPolicy,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
)
from constructs import Construct


class ImageHostingStack(Stack):
    """Stack for S3 and CloudFront infrastructure to host product images."""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Create S3 bucket and CloudFront distribution
        self.bucket, self.distribution = self._create_image_hosting_infrastructure()
        
        # Create outputs
        self._create_outputs()
    
    def _create_image_hosting_infrastructure(self) -> tuple[s3.Bucket, cloudfront.Distribution]:
        """Create S3 bucket and CloudFront distribution for hosting product images."""
        
        # Create S3 bucket with private access
        bucket = s3.Bucket(
            self,
            "ProductImagesBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.GET, s3.HttpMethods.HEAD],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    exposed_headers=["ETag"],
                    max_age=3600  # 1 hour in seconds
                )
            ],
            removal_policy=RemovalPolicy.RETAIN,  # Prevent accidental deletion
        )
        
        # Create Origin Access Identity for CloudFront
        oai = cloudfront.OriginAccessIdentity(
            self,
            "ProductImagesOAI",
            comment="OAI for chatgpt-apps-aws bucket"
        )
        
        # Grant OAI read access to bucket
        bucket.grant_read(oai)
        
        # Create response headers policy for CORS
        response_headers_policy = cloudfront.ResponseHeadersPolicy(
            self,
            "ProductImagesResponseHeaders",
            cors_behavior=cloudfront.ResponseHeadersCorsBehavior(
                access_control_allow_credentials=False,
                access_control_allow_origins=["*"],
                access_control_allow_methods=["GET", "HEAD"],
                access_control_allow_headers=["*"],
                access_control_expose_headers=["ETag"],
                access_control_max_age=Duration.hours(24),
                origin_override=True
            ),
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(
                    access_control_max_age=Duration.days(365),
                    include_subdomains=True,
                    override=True
                )
            ),
            custom_headers_behavior=cloudfront.ResponseCustomHeadersBehavior(
                custom_headers=[
                    cloudfront.ResponseCustomHeader(
                        header="Cache-Control",
                        value="public, max-age=86400, immutable",
                        override=True
                    )
                ]
            )
        )
        
        # Create CloudFront distribution
        distribution = cloudfront.Distribution(
            self,
            "ProductImagesCDN",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    bucket,
                    origin_access_identity=oai
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD,
                compress=True,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                response_headers_policy=response_headers_policy
            ),
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            http_version=cloudfront.HttpVersion.HTTP2_AND_3,
            enable_ipv6=True,
        )
        
        return bucket, distribution
    
    def _create_outputs(self) -> None:
        """Create CDK outputs for S3 and CloudFront resources."""
        
        CfnOutput(
            self,
            "ProductImagesBucketName",
            value=self.bucket.bucket_name,
            description="S3 bucket name for product images",
        )
        
        CfnOutput(
            self,
            "ProductImagesCDNDomain",
            value=self.distribution.distribution_domain_name,
            description="CloudFront distribution domain for product images",
            export_name="ImageHostingStack:ProductImagesCDNDomain",
        )
        
        CfnOutput(
            self,
            "ProductImagesCDNDistributionId",
            value=self.distribution.distribution_id,
            description="CloudFront distribution ID (for cache invalidation)",
        )

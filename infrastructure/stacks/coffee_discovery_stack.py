from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    RemovalPolicy,
    aws_cognito as cognito,
    aws_opensearchserverless as opensearch_serverless,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_dynamodb as dynamodb,
)
from constructs import Construct
import json
import os


class CoffeeDiscoveryStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get region for use in configurations
        region = self.region

        # Create Cognito User Pool
        user_pool = self._create_cognito_user_pool()
        
        # Create Cognito App Client
        user_pool_client = self._create_cognito_app_client(user_pool)
        
        # Create Lambda execution role
        lambda_role = self._create_lambda_execution_role()
        
        # Create DynamoDB table for shopping cart
        cart_table = self._create_cart_table()
        
        # Create DynamoDB table for OAuth client registrations
        oauth_clients_table = self._create_oauth_clients_table()

        # Create DynamoDB table for OAuth authorization codes
        oauth_auth_codes_table = self._create_oauth_auth_codes_table()

        # Create DynamoDB table for OAuth access tokens
        oauth_tokens_table = self._create_oauth_tokens_table()

        # Grant Lambda permissions to all tables
        cart_table.grant_read_write_data(lambda_role)
        oauth_clients_table.grant_read_write_data(lambda_role)
        oauth_auth_codes_table.grant_read_write_data(lambda_role)
        oauth_tokens_table.grant_read_write_data(lambda_role)
        
        # Add S3 read permissions to Lambda role
        self._add_s3_permissions_to_lambda(lambda_role)
        
        # Create OpenSearch Serverless collection
        opensearch_collection = self._create_opensearch_collection(lambda_role)
        
        # Create Lambda function for MCP server (without API_GATEWAY_URL initially)
        mcp_lambda = self._create_mcp_lambda(
            lambda_role,
            opensearch_collection,
            cart_table,
            oauth_clients_table,
            oauth_auth_codes_table,
            oauth_tokens_table,
            user_pool,
            user_pool_client,
            region
        )
        
        # Create API Gateway with OAuth and MCP endpoints
        api = self._create_api_gateway(
            user_pool,
            mcp_lambda
        )

        # Create CDK outputs
        self._create_outputs(
            user_pool,
            user_pool_client,
            opensearch_collection,
            api,
            region
        )

    def _create_cognito_user_pool(self) -> cognito.UserPool:
        """Create Cognito user pool with password policy."""
        user_pool = cognito.UserPool(
            self,
            "CoffeeDiscoveryUserPool",
            user_pool_name="coffee-discovery-users",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        return user_pool

    def _create_cognito_app_client(self, user_pool: cognito.UserPool) -> cognito.UserPoolClient:
        """Create Cognito app client with no client secret."""
        user_pool_client = cognito.UserPoolClient(
            self,
            "CoffeeDiscoveryAppClient",
            user_pool=user_pool,
            user_pool_client_name="coffee-discovery-client",
            generate_secret=False,  # Public client
            auth_flows=cognito.AuthFlow(
                admin_user_password=True,  # Enable ALLOW_ADMIN_USER_PASSWORD_AUTH for Lambda
                user_password=True,        # Keep ALLOW_USER_PASSWORD_AUTH for compatibility
                custom=False,
                user_srp=False,
            ),
            access_token_validity=Duration.minutes(60),
            refresh_token_validity=Duration.days(30),
            id_token_validity=Duration.minutes(60),
        )
        return user_pool_client

    def _create_cart_table(self) -> dynamodb.Table:
        """Create DynamoDB table for shopping cart storage."""
        cart_table = dynamodb.Table(
            self,
            "CoffeeCartTable",
            table_name="coffee-cart",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl"
        )
        return cart_table

    def _create_oauth_clients_table(self) -> dynamodb.Table:
        """Create DynamoDB table for OAuth client registrations."""
        oauth_clients_table = dynamodb.Table(
            self,
            "OAuthClientsTable",
            table_name="oauth-clients",
            partition_key=dynamodb.Attribute(
                name="client_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="expires_at"
        )
        return oauth_clients_table

    def _create_oauth_auth_codes_table(self) -> dynamodb.Table:
        """Create DynamoDB table for OAuth authorization codes (short-lived, single-use)."""
        return dynamodb.Table(
            self,
            "OAuthAuthCodesTable",
            table_name="oauth-auth-codes",
            partition_key=dynamodb.Attribute(
                name="code",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="expires_at"
        )

    def _create_oauth_tokens_table(self) -> dynamodb.Table:
        """Create DynamoDB table for OAuth access tokens."""
        return dynamodb.Table(
            self,
            "OAuthTokensTable",
            table_name="oauth-tokens",
            partition_key=dynamodb.Attribute(
                name="oauth_token",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="expires_at"
        )

    def _create_lambda_execution_role(self) -> iam.Role:
        """Create execution role for Lambda function."""
        lambda_role = iam.Role(
            self,
            "MCPLambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for Coffee Discovery MCP Lambda",
        )

        # Add CloudWatch Logs permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/*"],
            )
        )

        # Add Bedrock permissions for embeddings
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                ],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v1",
                ],
            )
        )

        # Add Cognito permissions for OAuth authentication
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:AdminInitiateAuth",
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:GetUser",
                ],
                resources=[f"arn:aws:cognito-idp:{self.region}:{self.account}:userpool/*"],
            )
        )

        return lambda_role
    
    def _add_s3_permissions_to_lambda(self, lambda_role: iam.Role) -> None:
        """Add S3 read permissions to Lambda role for product images bucket."""
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:ListBucket",
                ],
                resources=[
                    f"arn:aws:s3:::chatgpt-apps-aws-{self.account}",
                    f"arn:aws:s3:::chatgpt-apps-aws-{self.account}/*",
                ],
            )
        )

    def _create_opensearch_collection(
        self, lambda_role: iam.Role
    ) -> opensearch_serverless.CfnCollection:
        """Create OpenSearch Serverless collection with access and security policies."""
        
        # Create encryption policy
        encryption_policy = opensearch_serverless.CfnSecurityPolicy(
            self,
            "CoffeeProductsEncryptionPolicy",
            name="coffee-products-encryption",
            type="encryption",
            policy=json.dumps({
                "Rules": [
                    {
                        "ResourceType": "collection",
                        "Resource": ["collection/coffee-products"]
                    }
                ],
                "AWSOwnedKey": True
            }),
        )

        # Create network policy (public access)
        network_policy = opensearch_serverless.CfnSecurityPolicy(
            self,
            "CoffeeProductsNetworkPolicy",
            name="coffee-products-network",
            type="network",
            policy=json.dumps([
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": ["collection/coffee-products"]
                        }
                    ],
                    "AllowFromPublic": True
                }
            ]),
        )

        # Create collection
        collection = opensearch_serverless.CfnCollection(
            self,
            "CoffeeProductsCollection",
            name="coffee-products",
            type="VECTORSEARCH",
            description="Coffee product catalog with vector search",
        )
        collection.add_dependency(encryption_policy)
        collection.add_dependency(network_policy)

        # Create data access policy
        access_policy = opensearch_serverless.CfnAccessPolicy(
            self,
            "CoffeeProductsAccessPolicy",
            name="coffee-products-access",
            type="data",
            description="Data access policy for coffee products collection - updated",
            policy=json.dumps([
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": [f"collection/coffee-products"],
                            "Permission": [
                                "aoss:CreateCollectionItems",
                                "aoss:UpdateCollectionItems",
                                "aoss:DescribeCollectionItems"
                            ]
                        },
                        {
                            "ResourceType": "index",
                            "Resource": [f"index/coffee-products/*"],
                            "Permission": [
                                "aoss:CreateIndex",
                                "aoss:DescribeIndex",
                                "aoss:ReadDocument",
                                "aoss:WriteDocument",
                                "aoss:UpdateIndex",
                                "aoss:DeleteIndex"
                            ]
                        }
                    ],
                    "Principal": [
                        lambda_role.role_arn,
                        f"arn:aws:iam::{self.account}:root",
                        f"arn:aws:iam::{self.account}:role/Admin",
                        f"arn:aws:sts::{self.account}:assumed-role/Admin/*"
                    ]
                }
            ]),
        )
        access_policy.add_dependency(collection)

        # Add OpenSearch Serverless permissions to Lambda role
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "aoss:APIAccessAll",
                ],
                resources=[collection.attr_arn],
            )
        )

        return collection

    def _create_mcp_lambda(
        self,
        lambda_role: iam.Role,
        opensearch_collection: opensearch_serverless.CfnCollection,
        cart_table: dynamodb.Table,
        oauth_clients_table: dynamodb.Table,
        oauth_auth_codes_table: dynamodb.Table,
        oauth_tokens_table: dynamodb.Table,
        user_pool: cognito.UserPool,
        user_pool_client: cognito.UserPoolClient,
        region: str,
    ) -> lambda_.Function:
        """Create Lambda function for MCP server with all dependencies bundled together."""
        
        # Import CloudFront domain from ImageHostingStack via Fn::ImportValue
        # The value will be exported by ImageHostingStack with export name
        from aws_cdk import Fn
        cloudfront_domain = Fn.import_value("ImageHostingStack:ProductImagesCDNDomain")
        
        # Create Lambda function with all dependencies bundled
        mcp_function = lambda_.Function(
            self,
            "MCPServerFunction",
            function_name="coffee-discovery-mcp",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="integrated_handler.lambda_handler",  # Updated to use integrated handler
            code=lambda_.Code.from_asset(
                os.path.join(os.path.dirname(__file__), "../.."),
                exclude=[
                    ".DocumentRevisions-V100",
                    ".Spotlight-V100",
                    ".fseventsd",
                    ".Trashes",
                    ".TemporaryItems",
                    "infrastructure/.venv",
                    "infrastructure/cdk.out",
                    ".git",
                    "**/__pycache__",
                    "**/*.pyc",
                ],
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_11.bundling_image,
                    "command": [
                        "bash", "-c",
                        # Install dependencies
                        "pip install -r lambda/requirements.txt -t /asset-output && "
                        # Copy application code (including new integrated handler)
                        "cp lambda/mcp_handler.py /asset-output/ && "
                        "cp lambda/integrated_handler.py /asset-output/ && "
                        "cp lambda/oauth_handler.py /asset-output/ && "
                        "cp lambda/cognito_auth.py /asset-output/ && "
                        "cp -r mcp_server /asset-output/ && "
                        # Clean up unnecessary files to reduce package size
                        "find /asset-output -type d -name '__pycache__' -exec rm -rf {} + || true && "
                        "find /asset-output -type d -name 'tests' -exec rm -rf {} + || true"
                    ],
                }
            ),
            role=lambda_role,
            timeout=Duration.seconds(60),  # Increased for larger responses
            memory_size=1024,  # Increased for better performance
            architecture=lambda_.Architecture.ARM_64,  # Match the build architecture (ARM64 on Mac)
            environment={
                "OPENSEARCH_ENDPOINT": opensearch_collection.attr_collection_endpoint,
                "BEDROCK_MODEL_ID": "amazon.titan-embed-text-v1",
                "DYNAMODB_CART_TABLE": cart_table.table_name,
                "DYNAMODB_OAUTH_CLIENTS_TABLE": oauth_clients_table.table_name,
                "DYNAMODB_OAUTH_AUTH_CODES_TABLE": oauth_auth_codes_table.table_name,
                "DYNAMODB_OAUTH_TOKENS_TABLE": oauth_tokens_table.table_name,
                "CLOUDFRONT_DOMAIN": f"https://{cloudfront_domain}",
                # OAuth configuration
                "COGNITO_USER_POOL_ID": user_pool.user_pool_id,
                "COGNITO_CLIENT_ID": user_pool_client.user_pool_client_id,
            },
        )

        return mcp_function
    
    def _create_api_gateway(
        self,
        user_pool: cognito.UserPool,
        mcp_lambda: lambda_.Function,
    ) -> apigateway.RestApi:
        """Create API Gateway with OAuth and MCP endpoints."""
        
        # Create REST API
        api = apigateway.RestApi(
            self,
            "MCPServerAPI",
            rest_api_name="coffee-discovery-mcp-api",
            description="API Gateway for Coffee Discovery MCP Server with OAuth",
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                throttling_rate_limit=100,
                throttling_burst_limit=200,
            ),
        )
        
        # Create Lambda integration (without automatic permissions)
        lambda_integration = apigateway.LambdaIntegration(
            mcp_lambda,
            proxy=True
        )
        
        # Create /mcp resource
        mcp_resource = api.root.add_resource("mcp")
        
        # Add GET method for OAuth discovery
        mcp_resource.add_method(
            "GET",
            lambda_integration,
            authorization_type=apigateway.AuthorizationType.NONE,
        )
        
        # Add POST method for MCP JSON-RPC (with optional OAuth)
        mcp_resource.add_method(
            "POST",
            lambda_integration,
            authorization_type=apigateway.AuthorizationType.NONE,
        )
        
        # Create OAuth endpoints
        self._add_oauth_endpoints(api, mcp_lambda, lambda_integration, mcp_resource)
        
        # Add CORS support to /mcp
        mcp_resource.add_cors_preflight(
            allow_origins=["*"],
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization"],
        )
        
        return api
    
    def _add_oauth_endpoints(self, api: apigateway.RestApi, mcp_lambda: lambda_.Function, lambda_integration: apigateway.LambdaIntegration, mcp_resource: apigateway.Resource) -> None:
        """Add OAuth 2.0 endpoints to API Gateway at both root and /mcp levels."""
        
        # Create /.well-known resource at root level
        well_known_resource = api.root.add_resource(".well-known")
        
        # OAuth authorization server metadata at root
        oauth_auth_server_resource = well_known_resource.add_resource("oauth-authorization-server")
        oauth_auth_server_resource.add_method(
            "GET",
            lambda_integration,
            authorization_type=apigateway.AuthorizationType.NONE,
        )
        
        # OAuth protected resource metadata at root
        oauth_protected_resource = well_known_resource.add_resource("oauth-protected-resource")
        oauth_protected_resource.add_method(
            "GET",
            lambda_integration,
            authorization_type=apigateway.AuthorizationType.NONE,
        )
        
        # Create /oauth resource at root level
        oauth_resource = api.root.add_resource("oauth")
        
        # OAuth authorization endpoint at root
        authorize_resource = oauth_resource.add_resource("authorize")
        authorize_resource.add_method(
            "GET",
            lambda_integration,
            authorization_type=apigateway.AuthorizationType.NONE,
        )
        authorize_resource.add_method(
            "POST",
            lambda_integration,
            authorization_type=apigateway.AuthorizationType.NONE,
        )
        
        # OAuth token endpoint at root
        token_resource = oauth_resource.add_resource("token")
        token_resource.add_method(
            "POST",
            lambda_integration,
            authorization_type=apigateway.AuthorizationType.NONE,
        )
        
        # OAuth Dynamic Client Registration endpoint at root (RFC 7591)
        register_resource = oauth_resource.add_resource("register")
        register_resource.add_method(
            "POST",
            lambda_integration,
            authorization_type=apigateway.AuthorizationType.NONE,
        )
        
        # Add CORS to root OAuth endpoints
        for resource in [oauth_auth_server_resource, oauth_protected_resource, 
                        authorize_resource, token_resource, register_resource]:
            resource.add_cors_preflight(
                allow_origins=["*"],
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization"],
            )
        
        # ===== NOW ADD THE SAME ENDPOINTS UNDER /mcp/ =====
        
        # Create /mcp/.well-known resource
        mcp_well_known_resource = mcp_resource.add_resource(".well-known")
        
        # OAuth authorization server metadata under /mcp
        mcp_oauth_auth_server_resource = mcp_well_known_resource.add_resource("oauth-authorization-server")
        mcp_oauth_auth_server_resource.add_method(
            "GET",
            lambda_integration,
            authorization_type=apigateway.AuthorizationType.NONE,
        )
        
        # OAuth protected resource metadata under /mcp
        mcp_oauth_protected_resource = mcp_well_known_resource.add_resource("oauth-protected-resource")
        mcp_oauth_protected_resource.add_method(
            "GET",
            lambda_integration,
            authorization_type=apigateway.AuthorizationType.NONE,
        )
        
        # Create /mcp/oauth resource
        mcp_oauth_resource = mcp_resource.add_resource("oauth")
        
        # OAuth authorization endpoint under /mcp
        mcp_authorize_resource = mcp_oauth_resource.add_resource("authorize")
        mcp_authorize_resource.add_method(
            "GET",
            lambda_integration,
            authorization_type=apigateway.AuthorizationType.NONE,
        )
        mcp_authorize_resource.add_method(
            "POST",
            lambda_integration,
            authorization_type=apigateway.AuthorizationType.NONE,
        )
        
        # OAuth token endpoint under /mcp
        mcp_token_resource = mcp_oauth_resource.add_resource("token")
        mcp_token_resource.add_method(
            "POST",
            lambda_integration,
            authorization_type=apigateway.AuthorizationType.NONE,
        )
        
        # OAuth Dynamic Client Registration endpoint under /mcp (RFC 7591)
        mcp_register_resource = mcp_oauth_resource.add_resource("register")
        mcp_register_resource.add_method(
            "POST",
            lambda_integration,
            authorization_type=apigateway.AuthorizationType.NONE,
        )
        
        # Add CORS to /mcp OAuth endpoints
        for resource in [mcp_oauth_auth_server_resource, mcp_oauth_protected_resource, 
                        mcp_authorize_resource, mcp_token_resource, mcp_register_resource]:
            resource.add_cors_preflight(
                allow_origins=["*"],
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization"],
            )

    def _create_outputs(
        self,
        user_pool: cognito.UserPool,
        user_pool_client: cognito.UserPoolClient,
        opensearch_collection: opensearch_serverless.CfnCollection,
        api: apigateway.RestApi,
        region: str,
    ) -> None:
        """Create CDK outputs for easy access to resource information."""
        
        CfnOutput(
            self,
            "CognitoUserPoolId",
            value=user_pool.user_pool_id,
            description="Cognito User Pool ID",
        )

        CfnOutput(
            self,
            "CognitoClientId",
            value=user_pool_client.user_pool_client_id,
            description="Cognito App Client ID",
        )

        discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool.user_pool_id}/.well-known/openid-configuration"
        CfnOutput(
            self,
            "CognitoDiscoveryUrl",
            value=discovery_url,
            description="Cognito OIDC Discovery URL",
        )

        CfnOutput(
            self,
            "OpenSearchEndpoint",
            value=opensearch_collection.attr_collection_endpoint,
            description="OpenSearch Serverless Collection Endpoint",
        )

        CfnOutput(
            self,
            "MCPServerURL",
            value=f"{api.url}mcp",
            description="MCP Server API Gateway URL",
        )

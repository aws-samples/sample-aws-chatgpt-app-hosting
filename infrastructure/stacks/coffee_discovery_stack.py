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
)
from constructs import Construct
import json


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
        
        # Create OpenSearch Serverless collection
        opensearch_collection = self._create_opensearch_collection(lambda_role)
        
        # Create Lambda function for MCP server
        mcp_lambda = self._create_mcp_lambda(
            lambda_role,
            opensearch_collection,
            region
        )
        
        # Create API Gateway with Cognito authorizer
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
                user_password=True,
                custom=False,
                user_srp=False,
            ),
            access_token_validity=Duration.minutes(60),
            refresh_token_validity=Duration.days(30),
            id_token_validity=Duration.minutes(60),
        )
        return user_pool_client

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

        return lambda_role

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
        region: str,
    ) -> lambda_.Function:
        """Create Lambda function for MCP server with all dependencies bundled together."""
        
        # Create Lambda function with all dependencies bundled
        mcp_function = lambda_.Function(
            self,
            "MCPServerFunction",
            function_name="coffee-discovery-mcp",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="mcp_handler.lambda_handler",
            code=lambda_.Code.from_asset(
                "..",  # Start from project root
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_11.bundling_image,
                    "command": [
                        "bash", "-c",
                        # Install dependencies
                        "pip install -r lambda/requirements.txt -t /asset-output && "
                        # Copy application code
                        "cp lambda/mcp_handler.py /asset-output/ && "
                        "cp -r mcp_server /asset-output/ && "
                        # Clean up unnecessary files to reduce package size
                        "find /asset-output -type d -name '__pycache__' -exec rm -rf {} + || true && "
                        "find /asset-output -type d -name 'tests' -exec rm -rf {} + || true"
                    ],
                }
            ),
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=512,
            architecture=lambda_.Architecture.ARM_64,  # Match the build architecture (ARM64 on Mac)
            environment={
                "OPENSEARCH_ENDPOINT": opensearch_collection.attr_collection_endpoint,
                "BEDROCK_MODEL_ID": "amazon.titan-embed-text-v1",
            },
        )

        return mcp_function
    
    def _create_api_gateway(
        self,
        user_pool: cognito.UserPool,
        mcp_lambda: lambda_.Function,
    ) -> apigateway.RestApi:
        """Create API Gateway with Cognito authorizer."""
        
        # Create REST API
        api = apigateway.RestApi(
            self,
            "MCPServerAPI",
            rest_api_name="coffee-discovery-mcp-api",
            description="API Gateway for Coffee Discovery MCP Server",
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                throttling_rate_limit=100,
                throttling_burst_limit=200,
            ),
        )
        
        # Create /mcp resource
        mcp_resource = api.root.add_resource("mcp")
        
        # Add POST method without authorization (for ChatGPT compatibility)
        # Note: For production, implement OAuth discovery endpoints in Lambda
        mcp_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(mcp_lambda),
            authorization_type=apigateway.AuthorizationType.NONE,
        )
        
        # Add CORS support
        mcp_resource.add_cors_preflight(
            allow_origins=["*"],
            allow_methods=["POST", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization"],
        )
        
        return api

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

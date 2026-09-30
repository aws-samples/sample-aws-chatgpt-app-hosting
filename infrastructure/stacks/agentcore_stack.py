"""
AgentCore Stack (Part 2)

A single stack that provisions the full "AgentCore Gateway + Runtime" backend
for the ChatGPT Coffee Discovery app:

  * DynamoDB table for the shopping cart
  * OpenSearch Serverless (VECTORSEARCH) collection for semantic product search
  * An internal Cognito user pool used ONLY for the gateway -> runtime
    machine-to-machine (M2M) OAuth hop (never touched by ChatGPT)
  * A Bedrock AgentCore Runtime hosting the FastMCP streamable-HTTP server
    (bundled from ../mcp_server)
  * A Bedrock AgentCore Gateway with inbound auth = NONE, fronting the runtime
    through an outbound OAuth2 (M2M) credential provider

The reader deploys with `cdk deploy --all`, then pastes the `GatewayMcpUrl`
output into ChatGPT (Authentication = None).
"""
import os
import json
import shutil
import subprocess

from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    Fn,
    BundlingOptions,
    DockerImage,
    aws_dynamodb as dynamodb,
    aws_opensearchserverless as opensearchserverless,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_bedrockagentcore as agentcore,
)
from constructs import Construct

COLLECTION_NAME = "coffee-products"
INDEX_NAME = "coffee-products"
M2M_RESOURCE_SERVER = "mcp-runtime-server"
M2M_SCOPE_NAME = "invoke"
M2M_FULL_SCOPE = f"{M2M_RESOURCE_SERVER}/{M2M_SCOPE_NAME}"


def _container_runtime_available() -> bool:
    """Return True if a Docker-compatible container runtime is usable.

    CDK asset bundling shells out to `$CDK_DOCKER` (docker/finch). This mac
    aliases docker->finch, and finch runs inside a VM that must be started.
    We probe `<runtime> info` so that `cdk synth` still succeeds on machines
    where no container runtime is running (bundling is skipped and the raw
    source is staged instead). On a real deploy machine with finch/docker
    running, bundling proceeds and dependencies are installed into the asset.
    """
    runtime = os.environ.get("CDK_DOCKER", "docker")
    exe = shutil.which(runtime)
    if not exe:
        return False
    try:
        result = subprocess.run(
            [exe, "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
        return result.returncode == 0
    except Exception:
        return False


class AgentCoreStack(Stack):
    """Single stack containing the entire AgentCore Gateway + Runtime backend."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        region = self.region
        account = self.account

        # ------------------------------------------------------------------
        # a. DynamoDB cart table
        # ------------------------------------------------------------------
        cart_table = dynamodb.Table(
            self,
            "CoffeeCartTable",
            table_name="coffee-cart",
            partition_key=dynamodb.Attribute(
                name="user_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl",
        )

        # ------------------------------------------------------------------
        # b. OpenSearch Serverless collection (VECTORSEARCH)
        # ------------------------------------------------------------------
        encryption_policy = opensearchserverless.CfnSecurityPolicy(
            self,
            "CollectionEncryptionPolicy",
            name="coffee-products-enc",
            type="encryption",
            policy=json.dumps(
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": [f"collection/{COLLECTION_NAME}"],
                        }
                    ],
                    "AWSOwnedKey": True,
                }
            ),
        )

        network_policy = opensearchserverless.CfnSecurityPolicy(
            self,
            "CollectionNetworkPolicy",
            name="coffee-products-net",
            type="network",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{COLLECTION_NAME}"],
                            },
                            {
                                "ResourceType": "dashboard",
                                "Resource": [f"collection/{COLLECTION_NAME}"],
                            },
                        ],
                        "AllowFromPublic": True,
                    }
                ]
            ),
        )

        collection = opensearchserverless.CfnCollection(
            self,
            "CoffeeProductsCollection",
            name=COLLECTION_NAME,
            type="VECTORSEARCH",
            description="Coffee product catalog with vector embeddings",
        )
        collection.add_dependency(encryption_policy)
        collection.add_dependency(network_policy)

        # ------------------------------------------------------------------
        # c. Internal Cognito user pool (M2M gateway -> runtime hop ONLY)
        # ------------------------------------------------------------------
        user_pool = cognito.UserPool(
            self,
            "RuntimeM2MUserPool",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Domain prefix must be globally unique; derive from the account id.
        domain_prefix = f"coffee-ac-{account}"
        user_pool.add_domain(
            "RuntimeM2MDomain",
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=domain_prefix),
        )

        invoke_scope = cognito.ResourceServerScope(
            scope_name=M2M_SCOPE_NAME, scope_description="invoke runtime"
        )
        resource_server = user_pool.add_resource_server(
            "RuntimeResourceServer",
            identifier=M2M_RESOURCE_SERVER,
            scopes=[invoke_scope],
        )

        m2m_client = user_pool.add_client(
            "RuntimeM2MClient",
            generate_secret=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(client_credentials=True),
                scopes=[
                    cognito.OAuthScope.resource_server(resource_server, invoke_scope)
                ],
            ),
            auth_flows=cognito.AuthFlow(user_password=False),
        )

        # ------------------------------------------------------------------
        # d. AgentCore Runtime (FastMCP streamable-HTTP server)
        # ------------------------------------------------------------------
        mcp_server_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "mcp_server")
        )

        cloudfront_domain = Fn.import_value("ImageHostingStack:ProductImagesCDNDomain")

        # Bundle the MCP server dependencies into the runtime asset when a
        # container runtime is available; otherwise stage the source directly
        # so that `cdk synth` still succeeds (see _container_runtime_available).
        bundling = None
        if _container_runtime_available():
            bundling = BundlingOptions(
                image=DockerImage.from_registry(
                    "public.ecr.aws/sam/build-python3.11:latest-arm64"
                ),
                platform="linux/arm64",
                command=[
                    "bash",
                    "-c",
                    "pip install -r requirements.txt -t /asset-output && cp -r . /asset-output && find /asset-output -type d -name __pycache__ -prune -exec rm -rf {} + && find /asset-output -type f -name '*.pyc' -delete",
                ],
            )
        else:
            print(
                "[AgentCoreStack] No running container runtime detected "
                f"(CDK_DOCKER={os.environ.get('CDK_DOCKER', 'docker')}); staging "
                "mcp_server source WITHOUT dependency bundling. Start finch/docker "
                "before `cdk deploy` for a full dependency install."
            )

        runtime_artifact = agentcore.AgentRuntimeArtifact.from_code_asset(
            path=mcp_server_path,
            entrypoint=["server.py"],
            runtime=agentcore.AgentCoreRuntime.PYTHON_3_11,
            bundling=bundling,
        )

        runtime = agentcore.Runtime(
            self,
            "CoffeeRuntime",
            runtime_name="coffee_discovery_runtime",
            agent_runtime_artifact=runtime_artifact,
            protocol_configuration=agentcore.ProtocolType.MCP,
            authorizer_configuration=agentcore.RuntimeAuthorizerConfiguration.using_cognito(
                user_pool,
                [m2m_client],
                allowed_scopes=[M2M_FULL_SCOPE],
            ),
            environment_variables={
                "OPENSEARCH_ENDPOINT": collection.attr_collection_endpoint,
                "CLOUDFRONT_DOMAIN": f"https://{cloudfront_domain}",
                "CART_TABLE_NAME": cart_table.table_name,
                "AWS_REGION": region,
            },
        )

        # ------------------------------------------------------------------
        # e. Runtime role permissions
        # ------------------------------------------------------------------
        runtime.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v1"
                ],
            )
        )
        runtime.add_to_role_policy(
            iam.PolicyStatement(
                actions=["aoss:APIAccessAll"],
                resources=[collection.attr_arn],
            )
        )
        runtime.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["*"],
            )
        )
        cart_table.grant_read_write_data(runtime.role)

        # ------------------------------------------------------------------
        # f. OpenSearch data access policy (runtime role + account root)
        # ------------------------------------------------------------------
        data_access_policy = opensearchserverless.CfnAccessPolicy(
            self,
            "CollectionDataAccessPolicy",
            name="coffee-products-access",
            type="data",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{COLLECTION_NAME}"],
                                "Permission": [
                                    "aoss:CreateCollectionItems",
                                    "aoss:UpdateCollectionItems",
                                    "aoss:DescribeCollectionItems",
                                ],
                            },
                            {
                                "ResourceType": "index",
                                "Resource": [f"index/{COLLECTION_NAME}/*"],
                                "Permission": [
                                    "aoss:CreateIndex",
                                    "aoss:DescribeIndex",
                                    "aoss:ReadDocument",
                                    "aoss:WriteDocument",
                                    "aoss:UpdateIndex",
                                    "aoss:DeleteIndex",
                                ],
                            },
                        ],
                        "Principal": [
                            runtime.role.role_arn,
                            f"arn:aws:iam::{account}:root",
                        ],
                    }
                ]
            ),
        )
        data_access_policy.add_dependency(collection)

        # ------------------------------------------------------------------
        # g. Outbound M2M OAuth2 credential provider (gateway -> runtime)
        # ------------------------------------------------------------------
        oauth_provider = agentcore.OAuth2CredentialProvider.using_cognito(
            self,
            "RuntimeM2MProvider",
            client_id=m2m_client.user_pool_client_id,
            client_secret=m2m_client.user_pool_client_secret,
            authorization_endpoint=f"https://{domain_prefix}.auth.{region}.amazoncognito.com/oauth2/authorize",
            token_endpoint=f"https://{domain_prefix}.auth.{region}.amazoncognito.com/oauth2/token",
            issuer=f"https://cognito-idp.{region}.amazonaws.com/{user_pool.user_pool_id}",
            o_auth2_credential_provider_name="coffee-runtime-m2m",
        )

        # ------------------------------------------------------------------
        # h. AgentCore Gateway (inbound auth = NONE)
        # ------------------------------------------------------------------
        gateway = agentcore.Gateway(
            self,
            "CoffeeGateway",
            gateway_name="coffee-runtime-noauth",
            authorizer_configuration=agentcore.GatewayAuthorizer.with_no_auth(),
            protocol_configuration=agentcore.McpProtocolConfiguration(
                search_type=agentcore.McpGatewaySearchType.SEMANTIC,
                instructions="Coffee discovery MCP tools",
            ),
        )

        # ------------------------------------------------------------------
        # i. MCP server target pointing at the runtime invoke endpoint
        # ------------------------------------------------------------------
        runtime_invoke_endpoint = Fn.sub(
            "https://bedrock-agentcore.${AWS::Region}.amazonaws.com/runtimes/"
            "arn%3Aaws%3Abedrock-agentcore%3A${AWS::Region}%3A${AWS::AccountId}"
            "%3Aruntime%2F${Rid}/invocations?qualifier=DEFAULT",
            {"Rid": runtime.agent_runtime_id},
        )

        gateway.add_mcp_server_target(
            "RuntimeTarget",
            gateway_target_name="coffee-runtime-direct",
            endpoint=runtime_invoke_endpoint,
            credential_provider_configurations=[
                agentcore.GatewayCredentialProvider.from_oauth_identity(
                    oauth_provider, scopes=[M2M_FULL_SCOPE]
                )
            ],
        )

        # ------------------------------------------------------------------
        # j. Outputs
        # ------------------------------------------------------------------
        CfnOutput(
            self,
            "GatewayMcpUrl",
            value=gateway.gateway_url,
            description="MCP URL to paste into ChatGPT (Authentication = None)",
        )
        CfnOutput(
            self,
            "OpenSearchEndpoint",
            value=collection.attr_collection_endpoint,
            description="OpenSearch Serverless collection endpoint",
        )
        CfnOutput(
            self,
            "CartTableName",
            value=cart_table.table_name,
            description="DynamoDB cart table name",
        )

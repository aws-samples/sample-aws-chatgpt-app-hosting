# Requirements Document

## Introduction

This document specifies the requirements for a ChatGPT App for coffee product discovery called "Caffeine is All You Need". The system enables users to discover coffee beans through conversational interaction within the ChatGPT interface using the ChatGPT Apps SDK. The application consists of an MCP (Model Context Protocol) server that exposes tools and serves web components, backed by AWS infrastructure including Amazon Bedrock AgentCore Runtime for MCP server hosting and OpenSearch Serverless for product catalog storage. The infrastructure will be deployed using AWS CDK, and the MCP server will be implemented in Python 3 with FastMCP and uv package management.

## Glossary

- **ChatGPT App**: An application built with the ChatGPT Apps SDK that integrates with ChatGPT to provide custom functionality accessible from within the ChatGPT user interface
- **MCP Server**: Model Context Protocol server that exposes tools ChatGPT can call and serves web component resources rendered in iframes
- **Apps SDK**: OpenAI's framework for building apps for ChatGPT using the Model Context Protocol
- **AgentCore Runtime**: Amazon Bedrock service for hosting and running MCP servers with automatic session management, stateless operation, and built-in monitoring
- **FastMCP**: Python library from the official MCP SDK that simplifies creating MCP servers with stateless streamable-HTTP transport
- **Web Component**: HTML/CSS/JavaScript bundle served as an MCP resource and rendered in an iframe within ChatGPT
- **window.openai**: JavaScript API injected into web components that bridges the frontend with ChatGPT for tool calls and state management
- **Streamable HTTP**: Stateless HTTP transport protocol used by MCP servers to handle requests, required by AgentCore Runtime
- **Mcp-Session-Id**: Header automatically added by AgentCore Runtime for session isolation and continuity
- **OpenSearch Serverless**: AWS managed OpenSearch service that provides search and analytics capabilities without infrastructure management
- **Product Catalog**: Collection of coffee bean products with attributes including origin, roast level, flavor profile, and price
- **CDK**: AWS Cloud Development Kit for defining cloud infrastructure using code
- **Product Tile**: Visual representation of a coffee product including photo, name, and description rendered in the web component
- **Semantic Search**: Search capability using vector embeddings to understand meaning and context rather than just keyword matching
- **Coffee Bean Attributes**: Properties including country of origin, roast level, flavor profile, and price point
- **User Preferences**: User-specified criteria for coffee selection including taste preferences, budget, and origin preferences
- **Tool**: An MCP-exposed function that ChatGPT can call with structured parameters to perform actions
- **Structured Content**: JSON data returned by tools that ChatGPT can parse and reason about
- **Output Template**: MCP metadata that links a tool to a web component resource for rendering results
- **Docker Image Asset**: CDK construct that automatically builds Docker images from source directories and pushes them to ECR
- **ARM64 Platform**: Container architecture required by AgentCore Runtime for optimal performance
- **JWT Bearer Token**: JSON Web Token used for OAuth authentication, issued by Cognito and validated by AgentCore Runtime
- **Cognito User Pool**: AWS managed user directory that provides OAuth 2.0 and OIDC authentication for the MCP Server
- **OIDC Discovery Endpoint**: OpenID Connect discovery URL that provides OAuth configuration metadata for token validation
- **Demo/Development Authentication**: Authentication model using manually created Cognito test users with controlled access for demonstration purposes

## Requirements

### Requirement 1

**User Story:** As a coffee enthusiast, I want to describe my taste preferences in natural language, so that I can discover coffee beans that match my preferences without browsing through a catalog.

#### Acceptance Criteria

1. WHEN a user sends a message describing their coffee preferences THEN the MCP Server SHALL parse the preferences and extract relevant attributes
2. WHEN preference attributes are extracted THEN the MCP Server SHALL query the OpenSearch Serverless catalog using semantic search
3. WHEN search results are returned THEN the MCP Server SHALL rank products by relevance to user preferences
4. WHEN the user asks about specific attributes (e.g., "light roast from Ethiopia") THEN the MCP Server SHALL filter results to match those specific criteria
5. WHEN the user provides vague preferences THEN the MCP Server SHALL ask clarifying questions to refine the search

### Requirement 2

**User Story:** As a user, I want to see visual product tiles with photos, names, and descriptions rendered in an interactive web component, so that I can quickly evaluate coffee options while chatting.

#### Acceptance Criteria

1. WHEN the MCP Server registers resources THEN the system SHALL expose a web component resource with MIME type "text/html+skybridge"
2. WHEN coffee products are recommended THEN the tool SHALL return structured content including product arrays with photo URLs, names, descriptions, origins, roast levels, flavor profiles, and prices
3. WHEN the web component loads THEN the system SHALL access tool output via window.openai.toolOutput
4. WHEN the web component renders products THEN the system SHALL display them as visual tiles in a grid or list layout
5. WHEN a user interacts with the web component THEN the system SHALL use window.openai.callTool to invoke MCP tools and update the display

### Requirement 3

**User Story:** As a system administrator, I want the product catalog stored in OpenSearch Serverless, so that I can perform fast semantic searches across coffee bean attributes.

#### Acceptance Criteria

1. WHEN the system initializes THEN the OpenSearch Serverless collection SHALL contain coffee bean products from multiple countries of origin
2. WHEN the catalog is queried THEN the OpenSearch Serverless collection SHALL support vector search for semantic matching
3. WHEN products are stored THEN each product SHALL include fields for name, description, origin, roast level, flavor profile, price, and image URL
4. WHEN the catalog is populated THEN the system SHALL include at least 20 distinct coffee bean products with varied attributes
5. WHEN a search query is executed THEN the OpenSearch Serverless collection SHALL return results within 2 seconds

### Requirement 4

**User Story:** As a developer, I want the MCP Server implemented in Python 3 using FastMCP and uv for package management, so that I can maintain consistent dependencies and leverage modern Python tooling.

#### Acceptance Criteria

1. WHEN the MCP Server is built THEN the system SHALL use Python 3.11 or higher with FastMCP from the official MCP Python SDK
2. WHEN dependencies are managed THEN the system SHALL use uv for package installation and virtual environment management
3. WHEN the MCP Server starts THEN the system SHALL use FastMCP with host="0.0.0.0", port 8000, and stateless_http=True
4. WHEN the MCP Server runs THEN the system SHALL use transport="streamable-http" as required by AgentCore Runtime
5. WHEN the MCP Server receives requests THEN the system SHALL expose tools for search_products, get_product_details, and refine_preferences
6. WHEN tools are registered THEN each tool SHALL include OpenAI-specific metadata including "openai/outputTemplate" linking to the web component resource
7. WHEN the MCP Server processes requests THEN the system SHALL handle errors gracefully and return appropriate error messages

### Requirement 5

**User Story:** As a developer, I want the MCP Server hosted on Amazon Bedrock AgentCore Runtime, so that ChatGPT can connect to it securely with automatic session management and monitoring.

#### Acceptance Criteria

1. WHEN the infrastructure is deployed THEN the MCP Server SHALL run on Amazon Bedrock AgentCore Runtime as an ARM64 container
2. WHEN the MCP Server is deployed THEN the system SHALL be accessible via HTTPS at the AgentCore Runtime invocation endpoint with /mcp path
3. WHEN requests are received THEN AgentCore Runtime SHALL automatically add Mcp-Session-Id headers for session isolation
4. WHEN the MCP Server is configured THEN the system SHALL use Cognito user pool for OAuth authentication as required by AgentCore
5. WHEN the MCP Server is deployed THEN the system SHALL support CORS headers for ChatGPT's origin
6. WHEN the MCP Server encounters errors THEN AgentCore Runtime SHALL emit CloudWatch logs and metrics for monitoring

### Requirement 6

**User Story:** As a developer, I want all infrastructure deployed using AWS CDK only, so that I can manage the entire solution with a single deployment tool and simplified workflow.

#### Acceptance Criteria

1. WHEN infrastructure is provisioned THEN the system SHALL use AWS CDK written in Python with the aws-cdk-lib and aws-bedrock-agentcore-alpha modules
2. WHEN the MCP Server is containerized THEN the CDK SHALL use AgentRuntimeArtifact.from_asset() to automatically build the ARM64 Docker image from the source directory
3. WHEN the Docker image is built THEN the CDK SHALL automatically push it to Amazon ECR
4. WHEN the CDK stack is deployed THEN the system SHALL create the OpenSearch Serverless collection, Cognito user pool, AgentCore Runtime, and necessary IAM roles
5. WHEN the AgentCore Runtime is created THEN the CDK SHALL configure it with the Docker image reference, OAuth authorizer configuration, and MCP protocol type
6. WHEN the CDK stack is synthesized THEN the system SHALL generate valid CloudFormation templates
7. WHEN the infrastructure is updated THEN the CDK SHALL support incremental updates without data loss
8. WHEN the stack is destroyed THEN the CDK SHALL clean up all created resources including ECR images

### Requirement 7

**User Story:** As a product manager, I want the catalog to contain diverse coffee beans from "Caffeine is All You Need" store automatically populated during deployment, so that users can discover products across different preferences and budgets without manual data entry.

#### Acceptance Criteria

1. WHEN the product catalog is created THEN the system SHALL include coffee bean data in JSON format stored in the project repository
2. WHEN the catalog data is created THEN the system SHALL include coffee beans from at least 5 different countries of origin (e.g., Ethiopia, Colombia, Brazil, Kenya, Guatemala)
3. WHEN the catalog data is created THEN the system SHALL include products across at least 3 roast levels (light, medium, dark)
4. WHEN the catalog data is created THEN the system SHALL include products with varied flavor profiles (fruity, nutty, chocolatey, floral, earthy, spicy)
5. WHEN the catalog data is created THEN the system SHALL include products across at least 3 price tiers (budget: $12-15, mid-range: $16-22, premium: $23-35 per 12oz bag)
6. WHEN products are created THEN each product SHALL have a unique identifier, name, description, origin, roast level, flavor profile array, price, and image URL
7. WHEN the infrastructure is deployed THEN the system SHALL provide a Python script to load the product catalog JSON into OpenSearch Serverless
8. WHEN products are indexed THEN the system SHALL generate vector embeddings for semantic search based on product descriptions and flavor profiles
9. WHEN the catalog initialization completes THEN the system SHALL verify that all products are searchable in OpenSearch Serverless
10. WHEN the catalog is populated THEN the system SHALL include at least 20 distinct coffee bean products with realistic descriptions and varied attributes

### Requirement 8

**User Story:** As a developer, I want a simple Python script to populate OpenSearch with product data after CDK deployment, so that I can easily load and update the catalog without complex Lambda functions.

#### Acceptance Criteria

1. WHEN the project is created THEN the system SHALL include a Python script at scripts/load_catalog.py for loading product data
2. WHEN the script is created THEN the system SHALL use the OpenSearch Python client and boto3 for AWS authentication
3. WHEN the script is executed THEN the system SHALL read the product catalog JSON file from data/products.json
4. WHEN the script connects to OpenSearch THEN the system SHALL use AWS SigV4 authentication with the user's AWS credentials
5. WHEN products are indexed THEN the system SHALL create appropriate index mappings for text search and vector search fields
6. WHEN vector embeddings are needed THEN the system SHALL use Amazon Bedrock embeddings model (e.g., amazon.titan-embed-text-v1) to generate embeddings for product descriptions
7. WHEN the script indexes products THEN the system SHALL be idempotent using product IDs to avoid duplicates
8. WHEN the script completes successfully THEN the system SHALL output a summary of products indexed
9. WHEN the script encounters errors THEN the system SHALL provide clear error messages and exit with non-zero status code
10. WHEN the script is run THEN the system SHALL verify the OpenSearch collection exists and is accessible before attempting to load data

### Requirement 9

**User Story:** As a user, I want to refine my search through conversation, so that I can iteratively narrow down to the perfect coffee bean.

#### Acceptance Criteria

1. WHEN a user views initial recommendations THEN the system SHALL allow follow-up queries to refine results
2. WHEN a user asks to exclude certain attributes THEN the MCP Server SHALL filter out products matching those attributes
3. WHEN a user asks to see similar products THEN the MCP Server SHALL find products with similar flavor profiles or origins
4. WHEN a user changes preferences mid-conversation THEN the MCP Server SHALL update search criteria accordingly
5. WHEN a user asks for more details about a specific product THEN the MCP Server SHALL retrieve and return complete product information

### Requirement 10

**User Story:** As a developer, I want the system to integrate with ChatGPT using the Apps SDK connector pattern, so that users can access the coffee discovery experience without leaving ChatGPT.

#### Acceptance Criteria

1. WHEN the connector is added to ChatGPT THEN the user SHALL provide the HTTPS /mcp endpoint URL in ChatGPT Settings → Connectors
2. WHEN ChatGPT discovers the connector THEN the MCP Server SHALL respond to list_tools requests with tool metadata
3. WHEN ChatGPT calls a tool THEN the MCP Server SHALL return both text content for the conversation and structured content for the web component
4. WHEN the web component is rendered THEN ChatGPT SHALL load it in an iframe with the window.openai API injected
5. WHEN the connector is refreshed THEN ChatGPT SHALL pull the latest tool metadata and resource definitions from the MCP Server

### Requirement 11

**User Story:** As a developer, I want the web component to follow Apps SDK best practices, so that it provides a native ChatGPT experience.

#### Acceptance Criteria

1. WHEN the web component is built THEN the system SHALL create a single HTML file containing inline CSS and JavaScript
2. WHEN the web component initializes THEN the system SHALL listen for the "openai:set_globals" event to receive updated tool output
3. WHEN the user interacts with products in the component THEN the system SHALL call window.openai.callTool with the appropriate tool name and parameters
4. WHEN tool responses are received THEN the web component SHALL update its display using the structured content from the response
5. WHEN the component renders THEN the system SHALL use responsive design that works within ChatGPT's iframe constraints

### Requirement 12

**User Story:** As a developer, I want the MCP Server containerized and deployed using CDK Docker image assets, so that I can deploy everything with a single CDK command.

#### Acceptance Criteria

1. WHEN the MCP Server directory structure is created THEN the system SHALL include a Dockerfile that specifies ARM64 platform and Python 3.11+ base image
2. WHEN the Dockerfile is created THEN the system SHALL install dependencies from requirements.txt including mcp, FastMCP, and OpenSearch client libraries
3. WHEN the CDK stack defines the AgentCore Runtime THEN the system SHALL use AgentRuntimeArtifact.from_asset() pointing to the MCP server directory
4. WHEN the Docker image asset is configured THEN the system SHALL specify Platform.LINUX_ARM64 for AgentCore Runtime compatibility
5. WHEN CDK deploys the stack THEN the system SHALL automatically build the Docker image, push to ECR, and create the AgentCore Runtime
6. WHEN the deployment completes THEN the CDK SHALL output the AgentCore Runtime ARN and invocation endpoint URL
7. WHEN the MCP Server is invoked THEN the system SHALL use the AgentCore Runtime invocation endpoint with URL-encoded ARN and OAuth bearer token

### Requirement 13

**User Story:** As a developer, I want OAuth authentication configured between ChatGPT and AgentCore Runtime using demo/development mode with Cognito test users, so that the ChatGPT App can securely invoke the MCP Server with controlled access.

#### Acceptance Criteria

1. WHEN the CDK stack is deployed THEN the system SHALL create a Cognito user pool with OAuth 2.0 support and OIDC discovery endpoint
2. WHEN the Cognito user pool is configured THEN the CDK SHALL create an app client with USER_PASSWORD_AUTH and REFRESH_TOKEN_AUTH flows enabled and no client secret
3. WHEN the Cognito user pool is configured THEN the CDK SHALL set password policy with minimum 8 characters
4. WHEN the authentication model is implemented THEN the system SHALL use demo/development mode with manually created test users for controlled access
5. WHEN the AgentCore Runtime is created THEN the CDK SHALL configure it with RuntimeAuthorizerConfiguration.using_oauth() specifying the Cognito discovery URL and client ID
6. WHEN AgentCore Runtime is configured THEN the system SHALL validate incoming JWT tokens against the Cognito user pool issuer, client_id, and audience claims
7. WHEN the CDK deployment completes THEN the system SHALL output the Cognito discovery URL, client ID, and AgentCore Runtime invocation endpoint URL
8. WHEN ChatGPT connector is configured THEN the user SHALL provide the AgentCore Runtime invocation endpoint URL with URL-encoded ARN
9. WHEN ChatGPT connector requires authentication THEN the user SHALL configure OAuth 2.0 settings with the Cognito discovery URL and client ID from CDK outputs
10. WHEN ChatGPT invokes the MCP Server THEN the system SHALL include a valid OAuth bearer token in the Authorization header
11. WHEN bearer tokens expire THEN the system SHALL support token refresh using the REFRESH_TOKEN_AUTH flow

### Requirement 14

**User Story:** As a developer, I want comprehensive deployment and integration documentation, so that I can successfully deploy the solution and connect it to ChatGPT with simple commands.

#### Acceptance Criteria

1. WHEN the README is created THEN the system SHALL include prerequisites including AWS CLI, CDK CLI, Python 3.11+, uv, Docker, and required Python packages
2. WHEN the README covers deployment THEN the system SHALL include step-by-step instructions for deploying infrastructure using "cdk deploy"
3. WHEN the README covers data loading THEN the system SHALL include instructions for running "python scripts/load_catalog.py" after CDK deployment to populate the product catalog
4. WHEN the README covers data loading THEN the system SHALL explain that the script requires AWS credentials with permissions to write to OpenSearch Serverless and invoke Bedrock
5. WHEN the README covers CDK outputs THEN the system SHALL explain how to capture the Cognito discovery URL, client ID, user pool ID, OpenSearch endpoint, and AgentCore Runtime endpoint from CDK outputs
6. WHEN the README covers Cognito setup THEN the system SHALL include detailed instructions for creating test users using AWS CLI after CDK deployment
7. WHEN the README covers Cognito setup THEN the system SHALL include the shell script for automated test user creation and bearer token generation
8. WHEN the README covers Cognito setup THEN the system SHALL explain how to use AWS CLI to create additional test users and obtain access tokens
9. WHEN the README covers ChatGPT integration THEN the system SHALL include instructions for creating a ChatGPT account and enabling developer mode in Settings
10. WHEN the README covers connector setup THEN the system SHALL include exact steps for adding the connector in ChatGPT Settings → Connectors with the AgentCore Runtime endpoint URL from CDK outputs
11. WHEN the README covers authentication THEN the system SHALL include instructions for configuring OAuth 2.0 in the ChatGPT connector with Cognito discovery URL and client ID from CDK outputs
12. WHEN the README covers authentication THEN the system SHALL explain the authentication flow: ChatGPT obtains token from Cognito, includes token in requests to AgentCore, AgentCore validates token
13. WHEN the README covers testing THEN the system SHALL include example prompts and expected behaviors for validating the integration
14. WHEN the README covers user management THEN the system SHALL explain that this is a demo/development setup with manually created test users for controlled access
15. WHEN the README covers updating products THEN the system SHALL explain how to modify data/products.json and re-run the load script to update the catalog
16. WHEN the README is complete THEN the system SHALL include troubleshooting steps for common deployment, data loading, authentication, and integration issues
17. WHEN the README covers cleanup THEN the system SHALL include instructions for destroying all resources using "cdk destroy"

### Requirement 15

**User Story:** As a security administrator, I want to understand the authentication security model, so that I can assess the security posture and access controls of the deployed system.

#### Acceptance Criteria

1. WHEN the system is deployed THEN the AgentCore Runtime endpoint SHALL be publicly accessible via HTTPS for ChatGPT to reach it
2. WHEN requests are received THEN the system SHALL NOT allow anonymous access and SHALL require valid JWT bearer tokens
3. WHEN authentication is configured THEN the system SHALL use Cognito as the OAuth 2.0 identity provider for token issuance and validation
4. WHEN users access the system THEN only users with valid Cognito credentials SHALL be able to obtain bearer tokens
5. WHEN the demo/development model is used THEN access SHALL be controlled through manual creation of Cognito test users
6. WHEN bearer tokens are issued THEN the system SHALL enforce token expiration with default 60-minute lifetime
7. WHEN tokens expire THEN users SHALL use the refresh token flow to obtain new access tokens
8. WHEN the system is evaluated for security THEN the documentation SHALL clearly state this is a demo/development authentication model with controlled access, not anonymous public access

### Requirement 16

**User Story:** As a system administrator, I want comprehensive error handling and logging, so that I can troubleshoot issues and monitor system health.

#### Acceptance Criteria

1. WHEN errors occur in the MCP Server THEN the system SHALL log error details with timestamps and context
2. WHEN OpenSearch queries fail THEN the system SHALL return graceful error messages to the user
3. WHEN the AgentCore Runtime encounters issues THEN the system SHALL emit CloudWatch metrics and logs
4. WHEN invalid requests are received THEN the MCP Server SHALL validate input and return descriptive error messages
5. WHEN authentication failures occur THEN the system SHALL log failed authentication attempts with token validation errors
6. WHEN the system is monitored THEN the infrastructure SHALL provide metrics for request count, latency, error rates, and authentication failures

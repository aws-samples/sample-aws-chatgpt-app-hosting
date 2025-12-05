# Implementation Plan

- [x] 1. Create project structure and product catalog data
  - Set up directory structure for MCP server, CDK infrastructure, scripts, and data
  - Create product catalog JSON with 20+ diverse coffee products
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.10_

- [x] 1.1 Create directory structure
  - Create `mcp_server/` directory for MCP server code
  - Create `infrastructure/` directory for CDK code
  - Create `scripts/` directory for utility scripts
  - Create `data/` directory for product catalog
  - _Requirements: 7.1_

- [x] 1.2 Create product catalog JSON file
  - Create `data/products.json` with 20+ coffee products
  - Include products from 5+ countries (Ethiopia, Colombia, Brazil, Kenya, Guatemala)
  - Include 3 roast levels (light, medium, dark)
  - Include varied flavor profiles (fruity, nutty, chocolatey, floral, earthy, spicy)
  - Include 3 price tiers (budget $12-15, mid-range $16-22, premium $23-35)
  - Each product has: product_id, name, description, origin, roast_level, flavor_profile, price, image_url
  - _Requirements: 7.2, 7.3, 7.4, 7.5, 7.6, 7.10_

- [x] 2. Implement MCP Server core functionality
  - Create FastMCP server with stateless HTTP transport
  - Implement OpenSearch client for product search
  - Implement Bedrock client for embeddings generation
  - _Requirements: 4.1, 4.3, 4.4, 4.5_

- [x] 2.1 Set up MCP server project structure
  - Create `mcp_server/requirements.txt` with dependencies (mcp, fastmcp, opensearch-py, boto3)
  - Create `mcp_server/server.py` as main entry point
  - Create `mcp_server/Dockerfile` for ARM64 container
  - _Requirements: 4.1, 4.2_

- [x] 2.2 Implement FastMCP server initialization
  - Initialize FastMCP with host="0.0.0.0", port=8000, stateless_http=True
  - Configure transport="streamable-http"
  - Add health check endpoint at GET /
  - _Requirements: 4.3, 4.4_

- [x] 2.3 Implement OpenSearch client module
  - Create `mcp_server/opensearch_client.py`
  - Implement connection with AWS SigV4 authentication
  - Implement semantic search with vector embeddings
  - Implement filtered search with exact attribute matching
  - _Requirements: 1.2, 1.3, 1.4_

- [x] 2.4 Implement Bedrock embeddings module
  - Create `mcp_server/embeddings.py`
  - Implement embedding generation using amazon.titan-embed-text-v1
  - Add error handling and retry logic
  - _Requirements: 1.2_

- [x] 2.5 Write property test for preference parsing
  - **Property 1: Preference parsing robustness**
  - **Validates: Requirements 1.1**

- [x] 2.6 Write property test for filter application
  - **Property 4: Filter application correctness**
  - **Validates: Requirements 1.4**

- [x] 3. Implement MCP tools
  - Implement search_products tool
  - Implement get_product_details tool
  - Implement refine_preferences tool
  - Register tools with OpenAI metadata
  - _Requirements: 4.5, 4.6_

- [x] 3.1 Implement search_products tool
  - Create `mcp_server/tools.py`
  - Implement search_products(preferences: str, filters: Optional[dict])
  - Parse natural language preferences
  - Generate embeddings for semantic search
  - Query OpenSearch with vector + filter search
  - Return structured content with products array
  - Add "openai/outputTemplate" metadata
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.5, 4.6_

- [x] 3.2 Implement get_product_details tool
  - Implement get_product_details(product_id: str)
  - Query OpenSearch by product_id
  - Return complete product information
  - Add "openai/outputTemplate" metadata
  - _Requirements: 9.5, 4.5, 4.6_

- [x] 3.3 Implement refine_preferences tool
  - Implement refine_preferences(exclude: Optional[List[str]], similar_to: Optional[str], filters: Optional[dict])
  - Handle exclusion filters
  - Handle similarity search
  - Return refined product results
  - Add "openai/outputTemplate" metadata
  - _Requirements: 9.2, 9.3, 4.5, 4.6_

- [x] 3.4 Write property test for tool response structure
  - **Property 5: Tool response structure completeness**
  - **Validates: Requirements 2.2**

- [x] 3.5 Write property test for tool metadata
  - **Property 8: Tool metadata completeness**
  - **Validates: Requirements 4.6**

- [x] 3.6 Write property test for error handling
  - **Property 9: Error handling graceful degradation**
  - **Validates: Requirements 4.7**

- [x] 4. Implement web component
  - Create single HTML file with inline CSS and JavaScript
  - Implement product tile rendering
  - Implement window.openai integration
  - _Requirements: 2.1, 2.3, 2.4, 2.5, 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 4.1 Create web component HTML structure
  - Create `mcp_server/web_component.html`
  - Add HTML structure for product grid
  - Add CSS for product tiles and responsive layout
  - Style for ChatGPT iframe constraints
  - _Requirements: 10.1, 10.5_

- [x] 4.2 Implement JavaScript for product rendering
  - Access window.openai.toolOutput for initial products
  - Render products as tiles with image, name, origin, roast level, flavor profile, price
  - Implement grid/list layout
  - _Requirements: 2.3, 2.4_

- [x] 4.3 Implement window.openai integration
  - Listen for "openai:set_globals" event
  - Implement window.openai.callTool() for interactions
  - Handle tool responses and update display
  - _Requirements: 2.5, 10.2, 10.3, 10.4_

- [x] 4.4 Write property test for UI tool invocation
  - **Property 6: UI tool invocation correctness**
  - **Validates: Requirements 2.5**

- [x] 5. Register web component as MCP resource
  - Register ui://widget/coffee-discovery.html resource
  - Set MIME type to text/html+skybridge
  - Link tools to web component via outputTemplate
  - _Requirements: 2.1, 4.6_

- [x] 5.1 Implement resource registration
  - Register web component resource in FastMCP server
  - Set MIME type to "text/html+skybridge"
  - Add metadata: openai/widgetPrefersBorder: true
  - _Requirements: 2.1_

- [x] 5.2 Link tools to web component
  - Update all tool registrations with "openai/outputTemplate": "ui://widget/coffee-discovery.html"
  - _Requirements: 4.6_

- [x] 6. Implement data loading script
  - Create Python script to load products into OpenSearch
  - Generate embeddings for all products
  - Implement idempotent loading
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.9, 8.10_

- [x] 6.1 Create data loading script structure
  - Create `scripts/load_catalog.py`
  - Add command-line argument parsing
  - Add logging configuration
  - _Requirements: 8.1_

- [x] 6.2 Implement OpenSearch connection
  - Connect to OpenSearch Serverless using AWS SigV4 auth
  - Verify collection exists and is accessible
  - Create index with appropriate mappings (text + vector fields)
  - _Requirements: 8.2, 8.3, 8.10_

- [x] 6.3 Implement product loading logic
  - Read products from data/products.json
  - Generate embeddings using Bedrock Titan model
  - Index products with embeddings
  - Use product_id for idempotent updates
  - Output summary of products indexed
  - _Requirements: 8.1, 8.4, 8.5, 8.6_

- [x] 6.4 Implement error handling
  - Handle file not found errors (exit code 1)
  - Handle OpenSearch connection errors (exit code 2)
  - Handle Bedrock API errors (exit code 3)
  - Handle data validation errors (exit code 4)
  - Provide clear error messages
  - _Requirements: 8.7, 8.9_

- [x] 6.5 Write property test for embedding generation
  - **Property 10: Embedding generation completeness**
  - **Validates: Requirements 8.4**

- [x] 6.6 Write property test for idempotence
  - **Property 11: Data loading idempotence**
  - **Validates: Requirements 8.5**

- [x] 6.7 Write property test for error reporting
  - **Property 12: Error reporting consistency**
  - **Validates: Requirements 8.7**

- [x] 7. Implement AWS CDK infrastructure
  - Create CDK stack with all AWS resources
  - Configure Cognito user pool
  - Configure OpenSearch Serverless
  - Configure AgentCore Runtime with Docker image asset
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

- [x] 7.1 Set up CDK project structure
  - Create `infrastructure/` directory
  - Initialize CDK app with Python
  - Create `infrastructure/app.py` as entry point
  - Create `infrastructure/stacks/coffee_discovery_stack.py`
  - Create `infrastructure/requirements.txt` with CDK dependencies
  - _Requirements: 6.1_

- [x] 7.2 Implement Cognito user pool
  - Create Cognito user pool with password policy (min 8 chars)
  - Create app client with USER_PASSWORD_AUTH and REFRESH_TOKEN_AUTH flows
  - Configure no client secret (public client)
  - Set token expiration (60 min access, 30 days refresh)
  - Output user pool ID, client ID, and discovery URL
  - _Requirements: 13.1, 13.2, 13.3, 13.7_

- [x] 7.3 Implement OpenSearch Serverless collection
  - Create OpenSearch Serverless collection
  - Configure access policy for MCP server execution role
  - Configure security policy (encryption)
  - Output collection endpoint
  - _Requirements: 3.1, 3.2, 6.4_

- [x] 7.4 Implement AgentCore Runtime with Docker image asset
  - Use AgentRuntimeArtifact.from_asset() to build Docker image from mcp_server/
  - Specify Platform.LINUX_ARM64
  - Create AgentCore Runtime with MCP protocol
  - Configure OAuth authorizer with Cognito discovery URL and client ID
  - Set environment variables (OPENSEARCH_ENDPOINT, AWS_REGION, BEDROCK_MODEL_ID)
  - Create execution role with OpenSearch and Bedrock permissions
  - Output runtime ARN and invocation endpoint URL
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.2, 6.3, 6.4, 6.5, 6.6, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 13.5, 13.6, 13.7_

- [x] 7.5 Configure IAM roles and permissions
  - Create execution role for AgentCore Runtime
  - Add permissions for OpenSearch Serverless access
  - Add permissions for Bedrock API access
  - Add permissions for CloudWatch Logs
  - _Requirements: 6.4_

- [x] 7.6 Add CDK outputs
  - Output CognitoUserPoolId
  - Output CognitoClientId
  - Output CognitoDiscoveryUrl
  - Output OpenSearchEndpoint
  - Output AgentCoreRuntimeArn
  - Output AgentCoreInvocationUrl
  - _Requirements: 13.7, 14.5_

- [x] 8. Create Cognito user creation script
  - Create shell script to automate test user creation
  - Generate bearer tokens for testing
  - _Requirements: 13.6, 13.7, 13.8, 14.6, 14.7, 14.8_

- [x] 8.1 Create Cognito setup script
  - Create `scripts/create_test_user.sh`
  - Implement user pool client creation (if needed)
  - Implement user creation with admin-create-user
  - Implement permanent password setting
  - Implement token generation with initiate-auth
  - Output pool ID, discovery URL, client ID, and bearer token
  - _Requirements: 13.6, 13.7, 13.8, 14.6, 14.7, 14.8_

- [x] 9. Create comprehensive README documentation
  - Document prerequisites
  - Document deployment steps
  - Document ChatGPT integration steps
  - Document testing and troubleshooting
  - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8, 14.9, 14.10, 14.11, 14.12, 14.13, 14.14, 14.15, 14.16, 14.17_

- [x] 9.1 Create README with prerequisites section
  - Document AWS CLI installation and configuration
  - Document CDK CLI installation
  - Document Python 3.11+ requirement
  - Document uv installation
  - Document Docker installation
  - Document required Python packages
  - _Requirements: 14.1_

- [x] 9.2 Document deployment steps
  - Document "cdk bootstrap" for first-time setup
  - Document "cdk deploy" command
  - Document capturing CDK outputs
  - Document running data loading script
  - Document creating Cognito test user
  - _Requirements: 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8_

- [x] 9.3 Document ChatGPT integration
  - Document creating ChatGPT account
  - Document enabling developer mode in Settings
  - Document adding connector with AgentCore endpoint URL
  - Document configuring OAuth with Cognito discovery URL and client ID
  - Document authentication flow explanation
  - _Requirements: 14.9, 14.10, 14.11, 14.12_

- [x] 9.4 Document testing and troubleshooting
  - Document example prompts for testing
  - Document expected behaviors
  - Document demo/development authentication model
  - Document how to update products and re-run load script
  - Document common issues and solutions
  - Document cleanup with "cdk destroy"
  - _Requirements: 14.13, 14.14, 14.15, 14.16, 14.17_

- [x] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement visual product carousel using ChatGPT-native rendering
  - Research and implement the correct method for rendering visual GUI components in ChatGPT
  - Replace text-only responses with rich visual product displays
  - _Requirements: 2.1, 2.3, 2.4, 10.4_

- [x] 11.1 Research ChatGPT Apps SDK visual rendering capabilities
  - Investigate current ChatGPT Apps SDK documentation for supported visual components
  - Determine if custom HTML widgets are supported or if native components should be used
  - Document findings and recommended approach
  - _Requirements: 2.1, 10.4_

- [x] 11.2 Implement product carousel with images
  - Update tool responses to return data in format that ChatGPT can render visually
  - Ensure product images are displayed inline in ChatGPT interface
  - Implement scrollable carousel or grid layout for multiple products
  - Test that product photography images load and display correctly
  - _Requirements: 2.3, 2.4_

- [x] 11.3 Add interactive product selection
  - Enable users to click/select products from visual display
  - Implement callback to get_product_details when user selects a product
  - Ensure smooth interaction flow between visual display and conversation
  - _Requirements: 2.5, 10.3_

- [x] 11.4 Test visual rendering in ChatGPT
  - Deploy updated implementation
  - Test product carousel displays correctly in ChatGPT interface
  - Verify images load and are properly sized
  - Confirm user can interact with visual elements
  - _Requirements: 2.3, 2.4, 2.5, 10.4_

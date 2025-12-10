# ChatGPT App AWS

A ChatGPT App that helps users discover coffee beans through conversational interaction. Built with the ChatGPT Apps SDK using Model Context Protocol (MCP), hosted on Amazon Bedrock AgentCore Runtime, with semantic search powered by OpenSearch Serverless.

## Overview

This application enables users to:
- Describe coffee preferences in natural language
- View visual product tiles with photos and descriptions
- Filter by origin, roast level, flavor profile, and price
- Refine searches through conversation
- Get detailed product information

**Architecture:**
- **MCP Server**: Python FastMCP server exposing tools and web components
- **Hosting**: AWS Lambda (ARM64) with API Gateway
- **Web Component**: Interactive UI rendered in ChatGPT iframe
- **Product Catalog**: OpenSearch Serverless with vector embeddings
- **Authentication**: Cognito OAuth 2.0 (optional - currently disabled for testing)
- **Infrastructure**: AWS CDK for automated deployment

## Prerequisites

Before deploying this application, ensure you have the following installed and configured:

### Required Tools

1. **AWS CLI** (configured with credentials)
   - Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
   - Configure: `aws configure`
   - Verify: `aws sts get-caller-identity`

2. **AWS CDK CLI**
   - No installation needed - use `npx` to run CDK commands
   - Verify: `npx aws-cdk --version`

3. **Python 3.11 or higher**
   - Check version: `python3 --version`
   - Download: https://www.python.org/downloads/

4. **uv** (Python package manager)
   - Install: `pip install uv` or `brew install uv` (macOS)
   - Verify: `uv --version`

5. **Docker**
   - Install: https://docs.docker.com/get-docker/
   - Verify: `docker --version`
   - Ensure Docker daemon is running

### Python Packages

The required Python packages are specified in:
- `infrastructure/requirements.txt` - CDK dependencies
- `mcp_server/requirements.txt` - MCP server dependencies
- `scripts/` - Script dependencies (boto3, opensearch-py)

These will be installed during the deployment process.

### AWS Permissions

Your AWS credentials must have permissions for:
- CloudFormation (stack creation/updates)
- Cognito (user pool management)
- OpenSearch Serverless (collection creation)
- Bedrock (AgentCore Runtime, embeddings API)
- IAM (role creation)
- ECR (image push)
- CloudWatch (logs and metrics)

## Deployment

Follow these steps to deploy the Coffee Discovery app:

### Step 1: Install Python Dependencies

Create a virtual environment and install the required Python packages for CDK:

```bash
cd infrastructure
uv venv
source .venv/bin/activate  # On macOS/Linux
uv pip install -r requirements.txt
```

### Step 2: Bootstrap CDK (First-Time Setup)

If this is your first time using CDK in your AWS account/region:

```bash
npx aws-cdk bootstrap
```

This creates the necessary S3 buckets and IAM roles for CDK deployments.

### Step 3: Deploy Infrastructure

Deploy both stacks (ImageHostingStack and ChatGPTAppAWSStack):

```bash
# If using Finch instead of Docker, set this environment variable:
export CDK_DOCKER=finch

npx aws-cdk deploy --all --require-approval never
```

The deployment will:
1. **ImageHostingStack**: Create S3 bucket and CloudFront distribution for product images
2. **ChatGPTAppAWSStack**: 
   - Bundle the MCP server code and dependencies for Lambda (ARM64)
   - Create Cognito user pool and app client
   - Create OpenSearch Serverless collection
   - Create Lambda function with API Gateway endpoint
   - Set up IAM roles and permissions
   - Configure Lambda with CloudFront domain environment variable

**Deployment time:** Approximately 5-10 minutes

### Step 4: Capture CDK Outputs

After deployment completes, **save these output values** - you'll need them for subsequent steps:

```
ImageHostingStack.ProductImagesCDNDomain = dXXXXXXXXXXXXXX.cloudfront.net
ImageHostingStack.ProductImagesBucketName = imagehostingstack-productimagesbucket03bda4c8-XXXXXXXXXX

ChatGPTAppAWSStack.CognitoUserPoolId = us-east-1_XXXXXXXXX
ChatGPTAppAWSStack.CognitoClientId = XXXXXXXXXXXXXXXXXXXXXXXXXX
ChatGPTAppAWSStack.CognitoDiscoveryUrl = https://cognito-idp.us-east-1.amazonaws.com/us-east-1_XXXXXXXXX/.well-known/openid-configuration
ChatGPTAppAWSStack.OpenSearchEndpoint = https://XXXXX.us-east-1.aoss.amazonaws.com
ChatGPTAppAWSStack.MCPServerURL = https://XXXXXXXXXX.execute-api.us-east-1.amazonaws.com/prod/mcp
```

**Important:** The `MCPServerURL` is your MCP server endpoint that you'll use to connect ChatGPT.

**Tip:** Copy these values to a text file for easy reference.

### Step 5: Generate and Upload Product Images

Set the required environment variables from CDK outputs:

```bash
export OPENSEARCH_ENDPOINT=<OpenSearchEndpoint from CDK outputs>
export CLOUDFRONT_DOMAIN=<ProductImagesCDNDomain from CDK outputs>
export S3_BUCKET=<ProductImagesBucketName from CDK outputs>
```

Activate the virtual environment and generate AI images:

```bash
source infrastructure/.venv/bin/activate
python3 scripts/generate_all_images.py
```

This script will:
- Generate 24 AI product images using Amazon Bedrock Nova Canvas
- Upload images to S3 bucket
- Update `data/products.json` with CloudFront URLs
- Takes approximately 2 minutes to complete

**Expected output:**
```
Generating AI Images for All Products
[1/24] Processing: Ethiopian Yirgacheffe
  ✓ Image generated (181786 bytes)
  ✓ Uploaded: https://dXXXXXXXXXXXXXX.cloudfront.net/images/ethiopian-yirgacheffe-light.png
...
Summary:
  Total processed: 24
  Successful: 24
  Failed: 0
```

### Step 6: Create OpenSearch Index

Create the OpenSearch index with proper knn_vector mapping for semantic search:

```bash
python3 scripts/create_index.py
```

This creates the `coffee-products` index with:
- Text fields for product metadata
- knn_vector field for embeddings (dimension: 1536)
- Proper HNSW configuration for vector search

### Step 7: Load Product Catalog

Load products into OpenSearch with embeddings and CloudFront URLs:

```bash
python3 scripts/simple_load.py
```

This script will:
- Read products from `data/products.json` (24 coffee products with CloudFront URLs)
- Generate vector embeddings using Amazon Bedrock Titan
- Index products in OpenSearch Serverless with embeddings

**Expected output:**
```
Loading products from data/products.json...
Loaded 24 products

Using CloudFront image URLs from products.json...
  1/24: Ethiopian Yirgacheffe - ✅ https://dXXXXXXXXXXXXXX.cloudfront.net/images/...
  ...

Generating embeddings...
  1/24: Ethiopian Yirgacheffe - ✅ embedded
  ...

Indexing 24 products...
  1/24: Ethiopian Yirgacheffe - ✅ indexed
  ...

✅ Done!
```

**Requirements:**
- AWS credentials with permissions to:
  - Write to OpenSearch Serverless
  - Invoke Bedrock embeddings API (amazon.titan-embed-text-v1)
- `OPENSEARCH_ENDPOINT` environment variable set to the endpoint from CDK outputs

**Note:** 
- The script is idempotent - running it multiple times won't create duplicates
- Images are served via CloudFront CDN for fast delivery
- Vector embeddings enable semantic search capabilities

### Step 8: Create Cognito Test User

Create a test user for authentication:

#### Option A: Automated Script (Recommended)

Use the provided shell script:

```bash
export REGION=us-east-1
export USER_POOL_ID=<CognitoUserPoolId from CDK outputs>
export CLIENT_ID=<CognitoClientId from CDK outputs>
export USERNAME=testuser
export PASSWORD=TestPass123!

source scripts/create_test_user.sh
```

The script will:
1. Create the user in Cognito
2. Set a permanent password
3. Generate an access token
4. Output the bearer token for testing

#### Option B: Manual Creation

Create user:
```bash
aws cognito-idp admin-create-user \
  --user-pool-id <CognitoUserPoolId> \
  --username testuser \
  --temporary-password TempPass123! \
  --message-action SUPPRESS
```

Set permanent password:
```bash
aws cognito-idp admin-set-user-password \
  --user-pool-id <CognitoUserPoolId> \
  --username testuser \
  --password TestPass123! \
  --permanent
```

Generate access token:
```bash
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id <CognitoClientId> \
  --auth-parameters USERNAME=testuser,PASSWORD=TestPass123!
```

**Save the `AccessToken` from the response** - you'll use this as the bearer token.

## ChatGPT Integration

Now connect your deployed MCP server to ChatGPT:

### Step 1: Create ChatGPT Account

If you don't have one already:
1. Go to https://chat.openai.com
2. Sign up for an account
3. Verify your email

### Step 2: Enable Developer Mode

1. Click your profile icon in the bottom-left corner
2. Select **Settings**
3. Navigate to **Developer** section
4. Toggle **Developer mode** to ON

### Step 3: Add MCP Connector

1. In Settings, go to **Connectors** section
2. Click **Add Connector**
3. Enter the connector details:
   - **Name**: Coffee Discovery
   - **MCP Server URL**: Use the `MCPServerURL` from your CDK outputs
     - Example: `https://3jwjvipdl2.execute-api.us-east-1.amazonaws.com/prod/mcp`

### Step 4: Configure Authentication

**For Testing (Current Setup):**
1. Select **None** for Authentication
2. Save the connector configuration

**Note:** The current deployment has authentication disabled on the API Gateway endpoint to simplify testing. For production use, you should:
- Enable Cognito authorization on the API Gateway
- Configure OAuth in ChatGPT with your `CognitoClientId` and `CognitoDiscoveryUrl`
- Follow the OAuth flow to obtain access tokens

### Step 5: Test the Connection

Once configured, you can start using the Coffee Discovery connector in ChatGPT:

1. Start a new chat
2. Type a coffee-related query (e.g., "I want a fruity light roast coffee")
3. ChatGPT will automatically invoke the MCP server tools
4. Results will be displayed in an interactive web component

**Note:** Since authentication is currently disabled, anyone with the API Gateway URL can access the MCP server. For production deployments, enable Cognito authorization.

## Testing

### Example Prompts

Try these prompts in ChatGPT to test the integration:

1. **Basic search:**
   ```
   I want a fruity light roast coffee
   ```

2. **Filtered search:**
   ```
   Show me Ethiopian coffees under $20
   ```

3. **Refinement:**
   ```
   Find something similar to this one but darker
   ```

4. **Exclusion:**
   ```
   Show me more options but exclude dark roasts
   ```

5. **Specific attributes:**
   ```
   I'm looking for a medium roast with chocolatey notes from Colombia
   ```

### Expected Behaviors

**Product Display:**
- Products appear as visual tiles in an iframe
- Each tile shows: image, name, origin, roast level, flavor profile, price
- Grid layout with responsive design

**Conversation Flow:**
- ChatGPT understands natural language preferences
- Filters are applied correctly (origin, roast, price, flavor)
- Follow-up questions refine results
- Product details available on request

**Error Handling:**
- Invalid requests show user-friendly error messages
- System gracefully handles missing data
- Authentication errors prompt re-login

### Demo/Development Authentication Model

**Important:** This deployment uses a demo/development authentication model:

- Access is controlled through manually created Cognito test users
- The AgentCore endpoint is publicly accessible via HTTPS
- **No anonymous access** - valid JWT tokens required for all requests
- Suitable for demonstrations and development
- **Not recommended for production** without additional security controls

**For production deployments, consider:**
- Federating Cognito with corporate identity provider
- Implementing WAF rules for the AgentCore endpoint
- Adding rate limiting and DDoS protection
- Enabling CloudTrail for audit logging

## Updating Products

To modify the product catalog:

### Step 1: Edit Product Data

Edit `data/products.json` to add, remove, or modify products.

**Product schema:**
```json
{
  "product_id": "unique-kebab-case-id",
  "name": "Product Name",
  "description": "Detailed description (2-3 sentences)",
  "origin": "Country",
  "roast_level": "light|medium|dark",
  "flavor_profile": ["fruity", "chocolatey", "nutty"],
  "price": 18.99,
  "image_url": "https://example.com/image.jpg"
}
```

### Step 2: Re-run Load Script

```bash
python3 scripts/load_catalog.py
```

The script is idempotent:
- Existing products are updated (matched by `product_id`)
- New products are added
- Removed products remain in OpenSearch (manual deletion required)

### Step 3: Verify

Test in ChatGPT to confirm the changes are reflected in search results.

## Troubleshooting

### Common Issues and Solutions

#### Deployment Issues

**Problem:** CDK deploy fails with "Docker daemon not running"
```
Solution: Start Docker Desktop or Docker daemon
  macOS: Open Docker Desktop application
  Linux: sudo systemctl start docker
```

**Problem:** CDK deploy fails with insufficient permissions
```
Solution: Verify your AWS credentials have the required permissions
  Check: aws sts get-caller-identity
  Required: CloudFormation, Cognito, OpenSearch, Bedrock, IAM, ECR, CloudWatch
```

**Problem:** CDK bootstrap fails
```
Solution: Ensure you're in the correct AWS account and region
  Check: aws configure list
  Bootstrap: npx aws-cdk bootstrap aws://ACCOUNT-ID/REGION
```

#### Data Loading Issues

**Problem:** load_catalog.py fails with "OpenSearch connection error" or 403 Forbidden
```
Solution: OpenSearch Serverless permissions are eventually consistent
  1. Wait 2-5 minutes after CDK deployment completes
  2. Verify credentials: aws sts get-caller-identity
  3. Check access policy includes your role:
     export AWS_PAGER=""
     aws opensearchserverless get-access-policy --name coffee-products-access --type data
  4. Use the simple loader as a reliable alternative:
     python3 scripts/simple_load.py
  5. Ensure AWS_PAGER="" is set to avoid CLI commands hanging
  
  Note: The simple_load.py script:
  - Creates the index with proper knn_vector mapping
  - Generates embeddings for semantic search
  - Generates AI product images
  - Uses a minimal approach that handles permission timing issues better
  - Is the recommended approach if load_catalog.py encounters issues
```

**Problem:** load_catalog.py fails with "Bedrock API error"
```
Solution: Verify Bedrock access in your region
  Check: aws bedrock list-foundation-models --region us-east-1
  Ensure amazon.titan-embed-text-v1 is available
  Verify AWS credentials have Bedrock invoke permissions
```

**Problem:** Image generation fails or is very slow
```
Solution: Check Nova Canvas availability and quotas
  Verify Nova Canvas model is available: aws bedrock list-foundation-models --region us-east-1 | grep nova-canvas
  Check for throttling errors in the logs
  Use --skip-images flag to bypass image generation if needed
  Image generation takes ~3-5 seconds per product (normal)
  Consider running with --image-width 512 --image-height 512 for faster generation
```

**Problem:** Images not displaying in web component
```
Solution: Verify image data is present
  Check that products have image_base64 field in OpenSearch
  Verify web component is using getImageSource() function
  Check browser console for errors
  Ensure data URIs are properly formatted (data:image/png;base64,...)
  If issues persist, use --skip-images and rely on image_url fallback
```

**Problem:** Script reports "File not found: data/products.json"
```
Solution: Run the script from the project root directory
  cd /path/to/project
  python3 scripts/load_catalog.py
```

#### Authentication Issues

**Problem:** ChatGPT shows "Authentication failed"
```
Solution: Verify OAuth configuration
  Check CognitoDiscoveryUrl and CognitoClientId in connector settings
  Ensure test user exists and password is correct
  Try creating a new test user
```

**Problem:** Token expired errors
```
Solution: Re-authenticate in ChatGPT
  Access tokens expire after 60 minutes
  ChatGPT should automatically refresh using refresh token
  If issues persist, log out and log back in
```

**Problem:** "Invalid client" error
```
Solution: Verify Cognito app client configuration
  Check that client has USER_PASSWORD_AUTH flow enabled
  Verify no client secret is configured (public client)
  Confirm client ID matches CDK output
```

#### ChatGPT Integration Issues

**Problem:** Connector not appearing in ChatGPT
```
Solution: Verify developer mode is enabled
  Settings → Developer → Developer mode ON
  Refresh the page
  Try a different browser
```

**Problem:** "Endpoint not reachable" error
```
Solution: Verify API Gateway endpoint URL
  Check MCPServerURL from CDK outputs
  Ensure URL includes /mcp path
  Test endpoint: curl -X POST <endpoint-url> -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'
```

**Problem:** Web component not rendering
```
Solution: Check browser console for errors
  Verify window.openai API is available
  Check that tools return structured content
  Verify MIME type is text/html+skybridge
```

#### Search and Results Issues

**Problem:** No search results returned
```
Solution: Verify product catalog is loaded
  Re-run: python3 scripts/load_catalog.py
  Check OpenSearch has data (use AWS Console)
  Try broader search terms
```

**Problem:** Search results don't match filters
```
Solution: Check filter syntax in tool calls
  Verify product attributes in data/products.json
  Check OpenSearch index mappings
  Review MCP server logs in CloudWatch
```

**Problem:** Images not displaying in product tiles
```
Solution: Verify image URLs in products.json
  Check URLs are publicly accessible
  Ensure HTTPS URLs (not HTTP)
  Test URLs in browser
```

### Monitoring and Logs

**CloudWatch Logs:**
```bash
# View Lambda function logs
aws logs tail /aws/lambda/coffee-discovery-mcp --follow

# View recent errors
aws logs filter-pattern /aws/lambda/coffee-discovery-mcp --filter-pattern "ERROR"
```

**CloudWatch Metrics:**
- Lambda invocations
- Error rates
- Response latency
- Duration and memory usage

**Access metrics in AWS Console:**
CloudWatch → Metrics → Lambda → By Function Name → coffee-discovery-mcp

## Cleanup

To remove all deployed resources and avoid ongoing charges:

```bash
cd infrastructure
npx aws-cdk destroy
```

This will delete:
- Lambda function
- API Gateway
- OpenSearch Serverless collection (and all data)
- Cognito user pool (and all users)
- IAM roles
- CloudWatch log groups

**Note:** The destroy process takes approximately 5-10 minutes.

**Manual cleanup (if needed):**
- Check for any remaining CloudWatch log groups
- Confirm OpenSearch collection is deleted

## Architecture Details

### Technology Stack

- **MCP Server**: Python 3.11, FastMCP, uv
- **Web Component**: Vanilla HTML/CSS/JavaScript
- **Search**: OpenSearch Serverless with vector embeddings
- **Embeddings**: Amazon Bedrock Titan (amazon.titan-embed-text-v1)
- **Hosting**: AWS Lambda (ARM64) with API Gateway
- **Authentication**: Amazon Cognito (OAuth 2.0 / OIDC)
- **Infrastructure**: AWS CDK (Python)

### Key Features

- **Semantic Search**: Vector embeddings for understanding natural language
- **Stateless HTTP**: MCP server uses streamable-HTTP transport
- **Session Management**: Automatic via Mcp-Session-Id headers
- **Interactive UI**: Web component with window.openai API
- **Secure Access**: OAuth 2.0 with JWT token validation
- **Infrastructure as Code**: Single CDK command deployment

### Project Structure

```
.
├── data/
│   └── products.json              # Coffee product catalog
├── infrastructure/
│   ├── app.py                     # CDK app entry point
│   ├── requirements.txt           # CDK dependencies
│   └── stacks/
│       └── coffee_discovery_stack.py  # Main CDK stack
├── mcp_server/
│   ├── server.py                  # FastMCP server
│   ├── tools.py                   # MCP tool implementations
│   ├── opensearch_client.py       # OpenSearch integration
│   ├── embeddings.py              # Bedrock embeddings
│   ├── web_component.html         # UI component
│   ├── Dockerfile                 # Container definition
│   └── requirements.txt           # Server dependencies
├── scripts/
│   ├── load_catalog.py            # Data loading script
│   └── create_test_user.sh        # User creation script
└── README.md                      # This file
```

## Support and Contributing

### Getting Help

- Review the troubleshooting section above
- Check CloudWatch logs for error details
- Verify all prerequisites are installed
- Ensure AWS credentials have required permissions

### Known Limitations

- Demo/development authentication model (not production-ready)
- Manual test user creation required
- No user preference persistence
- No shopping cart or checkout functionality
- Single-region deployment

### Future Enhancements

- User preference persistence (DynamoDB)
- Shopping cart integration
- Multi-region deployment
- Advanced filtering and recommendations
- Inventory management
- Production-grade authentication

## License

This is a demonstration application for the ChatGPT Apps SDK.

## Acknowledgments

Built with:
- [ChatGPT Apps SDK](https://platform.openai.com/docs/guides/apps)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/)
- [OpenSearch](https://opensearch.org/)

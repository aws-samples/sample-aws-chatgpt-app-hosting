# Design Document

## Overview

This document provides the technical design for the "Caffeine is All You Need" ChatGPT App - a coffee product discovery application that integrates with ChatGPT using the Apps SDK and Model Context Protocol (MCP). The system enables users to discover coffee beans through natural language conversation, with visual product tiles rendered in an interactive web component.

The architecture consists of:
- **MCP Server**: Python-based FastMCP server hosted on Amazon Bedrock AgentCore Runtime
- **Web Component**: Single-page HTML/CSS/JavaScript interface rendered in ChatGPT's iframe
- **Product Catalog**: OpenSearch Serverless collection with vector search capabilities
- **Authentication**: Cognito-based OAuth 2.0 for secure access
- **Infrastructure**: AWS CDK for automated deployment

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         ChatGPT User                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ Natural Language Query
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ChatGPT Interface                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Web Component (iframe)                       │  │
│  │  - Product tiles with images                             │  │
│  │  - window.openai.callTool() for interactions            │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ HTTPS + OAuth Bearer Token
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Amazon Bedrock AgentCore Runtime                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  - Validates JWT tokens (Cognito)                        │  │
│  │  - Adds Mcp-Session-Id headers                           │  │
│  │  - Routes to MCP Server container                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ /mcp endpoint
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Server (FastMCP)                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Tools:                                                   │  │
│  │  - search_products(preferences)                          │  │
│  │  - get_product_details(product_id)                       │  │
│  │  - refine_preferences(filters)                           │  │
│  │                                                           │  │
│  │  Resources:                                               │  │
│  │  - ui://widget/coffee-discovery.html                     │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ Vector + Text Search
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              OpenSearch Serverless Collection                    │
│  - Product documents with embeddings                             │
│  - Vector search for semantic matching                           │
│  - Text search for exact attribute filtering                     │
└─────────────────────────────────────────────────────────────────┘
```

### Authentication Flow

```
┌──────────┐                    ┌──────────┐                    ┌──────────────┐
│ ChatGPT  │                    │ Cognito  │                    │  AgentCore   │
│  Client  │                    │User Pool │                    │   Runtime    │
└────┬─────┘                    └────┬─────┘                    └──────┬───────┘
     │                               │                                  │
     │ 1. OAuth Token Request        │                                  │
     │─────────────────────────────>│                                  │
     │                               │                                  │
     │ 2. JWT Bearer Token           │                                  │
     │<─────────────────────────────│                                  │
     │                               │                                  │
     │ 3. MCP Request + Bearer Token │                                  │
     │──────────────────────────────────────────────────────────────>│
     │                               │                                  │
     │                               │ 4. Validate Token                │
     │                               │<─────────────────────────────────│
     │                               │                                  │
     │                               │ 5. Token Valid                   │
     │                               │──────────────────────────────────>│
     │                               │                                  │
     │ 6. MCP Response               │                                  │
     │<──────────────────────────────────────────────────────────────│
     │                               │                                  │
```

## Components and Interfaces

### 1. MCP Server (FastMCP)

**Technology**: Python 3.11+, FastMCP, uv package manager

**Responsibilities**:
- Expose MCP tools for product search and discovery
- Serve web component HTML resource
- Query OpenSearch Serverless for products
- Generate embeddings for semantic search
- Return structured content for ChatGPT and web component

**Key Files**:
- `mcp_server/server.py` - Main FastMCP server
- `mcp_server/tools.py` - Tool implementations
- `mcp_server/opensearch_client.py` - OpenSearch integration
- `mcp_server/embeddings.py` - Bedrock embeddings generation
- `mcp_server/web_component.html` - UI resource
- `mcp_server/requirements.txt` - Python dependencies
- `mcp_server/Dockerfile` - Container definition

**MCP Tools**:

1. **search_products**
   - Input: `{ preferences: string, filters?: { origin?: string, roast_level?: string, price_range?: [number, number] } }`
   - Output: `{ products: Product[], message: string }`
   - Metadata: `openai/outputTemplate: "ui://widget/coffee-discovery.html"`

2. **get_product_details**
   - Input: `{ product_id: string }`
   - Output: `{ product: Product, message: string }`
   - Metadata: `openai/outputTemplate: "ui://widget/coffee-discovery.html"`

3. **refine_preferences**
   - Input: `{ exclude?: string[], similar_to?: string, filters?: object }`
   - Output: `{ products: Product[], message: string }`
   - Metadata: `openai/outputTemplate: "ui://widget/coffee-discovery.html"`

**MCP Resources**:

1. **ui://widget/coffee-discovery.html**
   - MIME type: `text/html+skybridge`
   - Contains: Complete HTML/CSS/JavaScript for product display
   - Metadata: `openai/widgetPrefersBorder: true`

### 2. Web Component

**Technology**: Vanilla HTML/CSS/JavaScript (single file)

**Responsibilities**:
- Render product tiles with images, names, descriptions
- Handle user interactions (click, filter, etc.)
- Call MCP tools via `window.openai.callTool()`
- Update display based on tool responses
- Listen for `openai:set_globals` events

**Key Features**:
- Responsive grid layout for product tiles
- Product card with image, name, origin, roast level, flavor profile, price
- Interactive elements (click for details, filter buttons)
- Smooth animations and transitions
- ChatGPT-native styling

**API Integration**:
```javascript
// Access initial tool output
const products = window.openai?.toolOutput?.products ?? [];

// Call MCP tool
const response = await window.openai.callTool('get_product_details', { 
  product_id: 'ethiopian-yirgacheffe-light' 
});

// Listen for updates
window.addEventListener('openai:set_globals', (event) => {
  const products = event.detail?.globals?.toolOutput?.products;
  renderProducts(products);
});
```

### 3. OpenSearch Serverless Collection

**Configuration**:
- Collection name: `coffee-products`
- Index name: `products`
- Capacity: On-demand (serverless)
- Encryption: AWS-managed keys

**Index Mapping**:
```json
{
  "mappings": {
    "properties": {
      "product_id": { "type": "keyword" },
      "name": { "type": "text" },
      "description": { "type": "text" },
      "origin": { "type": "keyword" },
      "roast_level": { "type": "keyword" },
      "flavor_profile": { "type": "keyword" },
      "price": { "type": "float" },
      "image_url": { "type": "keyword" },
      "description_embedding": {
        "type": "knn_vector",
        "dimension": 1536,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "nmslib"
        }
      }
    }
  }
}
```

**Query Patterns**:

1. **Semantic Search** (vector similarity):
```python
query = {
  "knn": {
    "description_embedding": {
      "vector": user_preference_embedding,
      "k": 10
    }
  }
}
```

2. **Filtered Search** (exact match + semantic):
```python
query = {
  "bool": {
    "must": [
      {
        "knn": {
          "description_embedding": {
            "vector": embedding,
            "k": 20
          }
        }
      }
    ],
    "filter": [
      { "term": { "origin": "Ethiopia" } },
      { "term": { "roast_level": "light" } },
      { "range": { "price": { "gte": 12, "lte": 20 } } }
    ]
  }
}
```

### 4. Cognito User Pool

**Configuration**:
- Pool name: `coffee-discovery-users`
- Password policy: Minimum 8 characters
- App client: No client secret (public client)
- Auth flows: USER_PASSWORD_AUTH, REFRESH_TOKEN_AUTH
- Token expiration: 60 minutes (access), 30 days (refresh)

**OIDC Discovery Endpoint**:
```
https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration
```

**Token Claims**:
- `iss`: Cognito issuer URL
- `client_id`: App client ID
- `aud`: Audience (app client ID)
- `exp`: Expiration timestamp
- `username`: Cognito username

### 5. AgentCore Runtime

**Configuration**:
- Runtime name: `coffee-discovery-mcp`
- Protocol: MCP
- Network: Public (HTTPS endpoint)
- Platform: ARM64
- Authorizer: Custom JWT (Cognito)

**Container Specifications**:
- Base image: `python:3.11-slim` (ARM64)
- Port: 8000
- Endpoint: `/mcp`
- Health check: GET `/` returns 200

**Environment Variables**:
- `OPENSEARCH_ENDPOINT`: OpenSearch Serverless endpoint
- `AWS_REGION`: Deployment region
- `BEDROCK_MODEL_ID`: Embeddings model ID

### 6. AWS CDK Stack

**Stack Name**: `CoffeeDiscoveryStack`

**Resources**:
1. Cognito User Pool + App Client
2. OpenSearch Serverless Collection + Access Policy
3. ECR Repository (auto-created by CDK)
4. AgentCore Runtime with Docker image asset
5. IAM Roles (execution role for AgentCore)
6. CloudWatch Log Groups

**Outputs**:
- `CognitoUserPoolId`
- `CognitoClientId`
- `CognitoDiscoveryUrl`
- `OpenSearchEndpoint`
- `AgentCoreRuntimeArn`
- `AgentCoreInvocationUrl`

## Data Models

### Product

```python
@dataclass
class Product:
    product_id: str          # Unique identifier (kebab-case)
    name: str                # Display name
    description: str         # Detailed description (2-3 sentences)
    origin: str              # Country of origin
    roast_level: str         # "light", "medium", "dark"
    flavor_profile: List[str] # ["fruity", "chocolatey", "nutty", etc.]
    price: float             # Price in USD for 12oz bag
    image_url: str           # URL to product image
    
    def to_dict(self) -> dict:
        return asdict(self)
```

### Search Request

```python
@dataclass
class SearchRequest:
    preferences: str                    # Natural language preferences
    filters: Optional[SearchFilters]    # Optional exact filters
    
@dataclass
class SearchFilters:
    origin: Optional[str]
    roast_level: Optional[str]
    price_range: Optional[Tuple[float, float]]
    flavor_profile: Optional[List[str]]
```

### Tool Response

```python
@dataclass
class ToolResponse:
    content: List[dict]           # Text content for ChatGPT conversation
    structured_content: dict      # Data for web component (products array)
    
    def to_mcp_response(self) -> dict:
        return {
            "content": self.content,
            "structuredContent": self.structured_content
        }
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Preference parsing robustness
*For any* user preference string, the MCP Server should parse it without crashing and extract valid attributes (or return empty attributes for unparseable input)
**Validates: Requirements 1.1**

### Property 2: Search execution completeness
*For any* set of extracted preference attributes, the MCP Server should execute an OpenSearch query and return results (even if empty)
**Validates: Requirements 1.2**

### Property 3: Result ranking consistency
*For any* search results returned, the products should be ordered by relevance scores in descending order
**Validates: Requirements 1.3**

### Property 4: Filter application correctness
*For any* combination of filter criteria (origin, roast level, price range), all returned products should match ALL specified filters
**Validates: Requirements 1.4**

### Property 5: Tool response structure completeness
*For any* product recommendation response, the structured content should include all required fields: product_id, name, description, origin, roast_level, flavor_profile, price, and image_url for each product
**Validates: Requirements 2.2**

### Property 6: UI tool invocation correctness
*For any* user interaction in the web component, calling window.openai.callTool should include the correct tool name and properly formatted parameters
**Validates: Requirements 2.5**

### Property 7: Product schema compliance
*For any* product stored in OpenSearch, it should contain all required fields: name, description, origin, roast_level, flavor_profile, price, and image_url
**Validates: Requirements 3.3**

### Property 8: Tool metadata completeness
*For any* registered MCP tool, it should include the "openai/outputTemplate" metadata field linking to the web component resource
**Validates: Requirements 4.6**

### Property 9: Error handling graceful degradation
*For any* invalid request to the MCP Server, the system should return an error response with a descriptive message and not crash
**Validates: Requirements 4.7**

### Property 10: Embedding generation completeness
*For any* product in the catalog, the system should generate a vector embedding for its description
**Validates: Requirements 8.4**

### Property 11: Data loading idempotence
*For any* product catalog, running the load script multiple times should result in the same products indexed (no duplicates based on product_id)
**Validates: Requirements 8.5**

### Property 12: Error reporting consistency
*For any* error encountered by the load script, the system should output a clear error message and exit with a non-zero status code
**Validates: Requirements 8.7**

### Property 13: Exclusion filter correctness
*For any* set of excluded attributes, all returned products should NOT match any of the excluded attributes
**Validates: Requirements 9.2**

### Property 14: Similarity search relevance
*For any* product used as a similarity reference, all returned similar products should share at least one flavor profile or the same origin
**Validates: Requirements 9.3**

### Property 15: Product detail retrieval completeness
*For any* valid product ID, the get_product_details tool should return all product fields
**Validates: Requirements 9.5**

## Error Handling

### MCP Server Error Handling

**Error Categories**:

1. **Input Validation Errors**
   - Invalid tool parameters
   - Missing required fields
   - Type mismatches
   - Response: 400-level error with descriptive message

2. **OpenSearch Errors**
   - Connection failures
   - Query timeouts
   - Index not found
   - Response: Graceful fallback with user-friendly message

3. **Bedrock Errors**
   - Embedding generation failures
   - Model throttling
   - Response: Retry with exponential backoff, fallback to text search

4. **Authentication Errors**
   - Invalid JWT token
   - Expired token
   - Response: 401 Unauthorized (handled by AgentCore)

**Error Response Format**:
```python
{
    "content": [
        {
            "type": "text",
            "text": "I encountered an error: {user_friendly_message}"
        }
    ],
    "structuredContent": {
        "error": True,
        "message": "{user_friendly_message}",
        "products": []
    }
}
```

**Logging Strategy**:
- All errors logged to CloudWatch with context
- Include: timestamp, error type, stack trace, request ID
- Structured logging using Python logging module
- Log levels: ERROR for failures, WARNING for retries, INFO for normal operations

### Web Component Error Handling

**Error Scenarios**:

1. **Tool Call Failures**
   - Network errors
   - Timeout
   - Response: Display error message in UI, allow retry

2. **Rendering Errors**
   - Invalid product data
   - Missing fields
   - Response: Skip invalid products, log to console

3. **window.openai Unavailable**
   - Not in ChatGPT context
   - Response: Display static message, disable interactions

**Error Display**:
```javascript
function displayError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    document.querySelector('#product-container').appendChild(errorDiv);
}
```

### Data Loading Script Error Handling

**Error Scenarios**:

1. **File Not Found**
   - products.json missing
   - Response: Clear error message, exit code 1

2. **OpenSearch Connection Failure**
   - Invalid endpoint
   - Authentication failure
   - Response: Detailed error with troubleshooting steps, exit code 2

3. **Bedrock API Errors**
   - Model not available
   - Throttling
   - Response: Retry with backoff, exit code 3 if all retries fail

4. **Data Validation Errors**
   - Invalid product schema
   - Missing required fields
   - Response: List invalid products, exit code 4

**Exit Codes**:
- 0: Success
- 1: File/configuration error
- 2: OpenSearch error
- 3: Bedrock error
- 4: Data validation error

## Testing Strategy

### Unit Testing

**Framework**: pytest

**Test Coverage**:

1. **MCP Server Tools**
   - Test each tool with valid inputs
   - Test error handling with invalid inputs
   - Mock OpenSearch and Bedrock clients
   - Verify response structure

2. **OpenSearch Client**
   - Test query construction
   - Test result parsing
   - Mock OpenSearch responses

3. **Embeddings Generation**
   - Test embedding generation
   - Test caching behavior
   - Mock Bedrock API

4. **Data Loading Script**
   - Test JSON parsing
   - Test index creation
   - Test idempotence
   - Mock OpenSearch and Bedrock

**Example Unit Test**:
```python
def test_search_products_valid_input():
    # Arrange
    mock_opensearch = Mock()
    mock_opensearch.search.return_value = {
        "hits": {"hits": [{"_source": sample_product}]}
    }
    
    # Act
    result = search_products("fruity light roast", mock_opensearch)
    
    # Assert
    assert len(result["products"]) > 0
    assert all("product_id" in p for p in result["products"])
```

### Property-Based Testing

**Framework**: Hypothesis (Python)

**Configuration**: Minimum 100 iterations per property test

**Property Tests**:

Each property test will be tagged with: `**Feature: chatgpt-coffee-discovery-app, Property {number}: {property_text}**`

1. **Property 1: Preference parsing robustness**
   - Generate random preference strings
   - Verify no crashes and valid attribute extraction

2. **Property 4: Filter application correctness**
   - Generate random filter combinations
   - Verify all results match filters

3. **Property 5: Tool response structure completeness**
   - Generate random product sets
   - Verify all required fields present

4. **Property 7: Product schema compliance**
   - Generate random products
   - Verify schema compliance

5. **Property 11: Data loading idempotence**
   - Load same data twice
   - Verify identical state

**Example Property Test**:
```python
from hypothesis import given, strategies as st

@given(
    origin=st.sampled_from(["Ethiopia", "Colombia", "Brazil", "Kenya"]),
    roast_level=st.sampled_from(["light", "medium", "dark"]),
    price_range=st.tuples(
        st.floats(min_value=10, max_value=20),
        st.floats(min_value=20, max_value=40)
    )
)
def test_filter_application_correctness(origin, roast_level, price_range):
    """
    **Feature: chatgpt-coffee-discovery-app, Property 4: Filter application correctness**
    **Validates: Requirements 1.4**
    
    For any combination of filter criteria, all returned products 
    should match ALL specified filters.
    """
    # Arrange
    filters = {
        "origin": origin,
        "roast_level": roast_level,
        "price_range": price_range
    }
    
    # Act
    results = search_products_with_filters(filters)
    
    # Assert
    for product in results:
        assert product["origin"] == origin
        assert product["roast_level"] == roast_level
        assert price_range[0] <= product["price"] <= price_range[1]
```

### Integration Testing

**Scope**: End-to-end testing of MCP Server with real OpenSearch and Bedrock

**Test Scenarios**:

1. **Full Search Flow**
   - Send preference query
   - Verify OpenSearch query execution
   - Verify embedding generation
   - Verify response structure

2. **Authentication Flow**
   - Test with valid JWT token
   - Test with invalid token
   - Test with expired token

3. **Web Component Integration**
   - Load component in test environment
   - Simulate tool calls
   - Verify UI updates

**Test Environment**:
- Local OpenSearch Serverless (or LocalStack)
- Mock Bedrock API
- Test Cognito user pool

### Manual Testing

**ChatGPT Integration Testing**:

1. Deploy to development environment
2. Create test Cognito user
3. Configure ChatGPT connector
4. Test conversation flows:
   - "I want a fruity light roast"
   - "Show me Ethiopian coffees under $20"
   - "Find something similar to this one"
   - "Exclude dark roasts"

**Expected Behaviors**:
- Products displayed in tiles
- Filters applied correctly
- Conversation flows naturally
- Error messages are user-friendly

## Deployment Architecture

### CDK Stack Structure

```
CoffeeDiscoveryStack
├── Cognito User Pool
│   ├── User Pool
│   └── App Client (no secret)
├── OpenSearch Serverless
│   ├── Collection
│   ├── Access Policy
│   └── Security Policy
├── AgentCore Runtime
│   ├── ECR Repository (auto-created)
│   ├── Docker Image Asset (ARM64)
│   ├── Runtime Configuration
│   └── Execution Role
└── Outputs
    ├── CognitoUserPoolId
    ├── CognitoClientId
    ├── CognitoDiscoveryUrl
    ├── OpenSearchEndpoint
    ├── AgentCoreRuntimeArn
    └── AgentCoreInvocationUrl
```

### Docker Image Build

**Dockerfile**:
```dockerfile
FROM --platform=linux/arm64 python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy requirements and install dependencies
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run server
CMD ["python", "server.py"]
```

**CDK Docker Asset**:
```python
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk.aws_bedrock_agentcore_alpha import (
    AgentRuntimeArtifact,
    Runtime,
    RuntimeAuthorizerConfiguration,
    ProtocolType
)

# Build and push Docker image
artifact = AgentRuntimeArtifact.from_asset(
    directory="./mcp_server",
    platform=ecr_assets.Platform.LINUX_ARM64
)

# Create AgentCore Runtime
runtime = Runtime(
    self, "CoffeeDiscoveryRuntime",
    runtime_name="coffee-discovery-mcp",
    agent_runtime_artifact=artifact,
    authorizer_configuration=RuntimeAuthorizerConfiguration.using_oauth(
        discovery_url=f"https://cognito-idp.{region}.amazonaws.com/{user_pool.user_pool_id}/.well-known/openid-configuration",
        client_id=user_pool_client.user_pool_client_id
    ),
    protocol_configuration=ProtocolType.MCP,
    environment_variables={
        "OPENSEARCH_ENDPOINT": opensearch_collection.attr_collection_endpoint,
        "AWS_REGION": region,
        "BEDROCK_MODEL_ID": "amazon.titan-embed-text-v1"
    }
)
```

### Deployment Steps

1. **Prerequisites**:
   - AWS CLI configured
   - CDK CLI installed (`npm install -g aws-cdk`)
   - Python 3.11+
   - uv installed
   - Docker running

2. **Deploy Infrastructure**:
   ```bash
   cd infrastructure
   cdk bootstrap  # First time only
   cdk deploy
   ```

3. **Load Product Catalog**:
   ```bash
   python scripts/load_catalog.py
   ```

4. **Create Test User**:
   ```bash
   export REGION=us-west-2
   export USERNAME=testuser
   export PASSWORD=TestPass123!
   source scripts/create_test_user.sh
   ```

5. **Configure ChatGPT**:
   - Enable developer mode in ChatGPT Settings
   - Add connector with AgentCore endpoint URL
   - Configure OAuth with Cognito discovery URL and client ID
   - Test with sample prompts

### Monitoring and Observability

**CloudWatch Metrics**:
- AgentCore Runtime invocations
- MCP Server response times
- OpenSearch query latency
- Bedrock API calls
- Error rates

**CloudWatch Logs**:
- AgentCore Runtime logs: `/aws/bedrock-agentcore/runtime/{runtime-name}`
- MCP Server logs: Structured JSON logs
- Data loading script logs: Local output

**Alarms**:
- High error rate (> 5%)
- High latency (> 2 seconds)
- Authentication failures (> 10/minute)

**Dashboards**:
- Request volume over time
- Error rate by error type
- Latency percentiles (p50, p95, p99)
- OpenSearch query performance

## Security Considerations

### Authentication and Authorization

**OAuth 2.0 Flow**:
1. ChatGPT obtains token from Cognito using USER_PASSWORD_AUTH
2. Token includes claims: iss, client_id, aud, exp, username
3. AgentCore validates token against Cognito OIDC discovery
4. Valid requests forwarded to MCP Server

**Token Security**:
- Tokens expire after 60 minutes
- Refresh tokens valid for 30 days
- No client secret (public client pattern)
- Tokens transmitted over HTTPS only

**Access Control**:
- Demo/development mode: Manually created test users
- Production consideration: Federate with corporate IdP
- AgentCore endpoint publicly accessible but requires valid token
- OpenSearch access restricted to MCP Server execution role

### Data Security

**Encryption**:
- Data in transit: TLS 1.2+ for all connections
- Data at rest: AWS-managed encryption for OpenSearch
- Secrets: No hardcoded credentials, use IAM roles

**PII Handling**:
- No PII stored in product catalog
- User preferences not persisted
- Conversation history managed by ChatGPT

**Network Security**:
- AgentCore Runtime: Public endpoint (required for ChatGPT)
- OpenSearch Serverless: VPC endpoint (private)
- Cognito: Public endpoint (AWS managed)

### Compliance

**Demo/Development Considerations**:
- Not suitable for production without additional controls
- Test users should use non-production credentials
- Product data is fictional and non-sensitive
- No customer data collected or stored

**Production Recommendations**:
- Implement WAF rules for AgentCore endpoint
- Enable CloudTrail for audit logging
- Federate Cognito with corporate IdP
- Implement rate limiting
- Add DDoS protection

## Future Enhancements

### Phase 2 Features

1. **User Preferences Persistence**
   - Store user preferences in DynamoDB
   - Personalized recommendations based on history

2. **Shopping Cart Integration**
   - Add to cart functionality
   - Checkout flow

3. **Inventory Management**
   - Real-time stock levels
   - Out-of-stock notifications

4. **Advanced Search**
   - Flavor profile similarity
   - Brewing method recommendations
   - Price alerts

### Scalability Improvements

1. **Caching Layer**
   - Redis for frequently accessed products
   - Embedding cache to reduce Bedrock calls

2. **Performance Optimization**
   - Batch embedding generation
   - Query result caching
   - CDN for product images

3. **Multi-Region Deployment**
   - Global OpenSearch replication
   - Regional AgentCore Runtimes
   - Latency-based routing

### Operational Improvements

1. **Automated Testing**
   - CI/CD pipeline with automated tests
   - Canary deployments
   - Rollback automation

2. **Enhanced Monitoring**
   - Distributed tracing with X-Ray
   - Custom business metrics
   - Anomaly detection

3. **Cost Optimization**
   - OpenSearch capacity planning
   - Bedrock API call optimization
   - Reserved capacity for predictable workloads

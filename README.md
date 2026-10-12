# Host a ChatGPT App MCP Server on Amazon Bedrock AgentCore

A ChatGPT App that helps users discover and buy coffee beans through conversation. The app is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server built with the [ChatGPT Apps SDK](https://platform.openai.com/docs/guides/apps), hosted on **Amazon Bedrock AgentCore Runtime** and fronted by an **AgentCore Gateway**. ChatGPT connects to a single Gateway URL with no authentication configuration.

The backend is provisioned with the **AgentCore CLI** (`@aws/agentcore`), which bootstraps CDK and manages the deploy/teardown lifecycle for you. No Docker or Finch is required: the runtime is packaged as a CodeZip artifact.

This is the companion code for the AWS blog post *Build ChatGPT Apps with MCP Servers and AWS Infrastructure, Part 2*. Part 1 ([blog](https://aws.amazon.com/blogs/industries/build-chatgpt-apps-with-mcp-servers-and-aws-infrastructure/)) hosted the same MCP server on AWS Lambda + API Gateway; that code is preserved at the [`part-1-lambda`](../../tree/part-1-lambda) tag.

> **⚠️ Security notice:** This is a demo, not a production reference. The Gateway accepts unauthenticated requests and OpenSearch Serverless uses public network access. See [Adding authentication](#adding-authentication) before exposing anything real.

## What the app does

- Search a coffee catalog in natural language ("fruity light roast under $20")
- Render results as interactive product tiles inside ChatGPT
- Refine by origin, roast level, flavor profile, price, or similarity
- Add items to a persistent shopping cart and view/update it

## Architecture

```
ChatGPT ──(MCP, no auth)──▶ AgentCore Gateway ──(IAM / SigV4)──▶ AgentCore Runtime
                                                                     │  mcp_server/
                                     ┌───────────────────────────────┼──────────────────┐
                                     ▼                               ▼                  ▼
                              OpenSearch Serverless           DynamoDB (coffee-cart)   Bedrock Titan
                              hybrid + vector search          cart state               embeddings

Product images: S3 ──▶ CloudFront (same stack)
```

- **AgentCore Runtime** hosts the FastMCP server (`mcp_server/`) as a streamable-HTTP MCP endpoint, packaged by the CLI as a CodeZip artifact (no container runtime needed).
- **AgentCore Gateway** exposes the runtime to ChatGPT. Inbound auth is `NONE`; the Gateway authenticates to the runtime with its own IAM role (SigV4, the `GATEWAY_IAM_ROLE` outbound credential provider) — there is no Cognito pool and ChatGPT never sees it.
- **OpenSearch Serverless** stores the catalog with Titan embeddings for hybrid (keyword + semantic) search.
- **DynamoDB** persists cart state across the conversation.
- **S3 + CloudFront** serve the product images referenced by the widgets, provisioned in the same CDK stack.

An editable version of this diagram is in [`architecture.drawio`](architecture.drawio) (open with [draw.io](https://app.diagrams.net/) or the VS Code Draw.io extension).

## Prerequisites

- AWS CLI with credentials (`aws sts get-caller-identity` works)
- Node.js 20+ (the AgentCore CLI runs via `npx -y @aws/agentcore@0.31.1 <cmd>`)
- Python 3.11+ and [`uv`](https://github.com/astral-sh/uv) (for the data-setup scripts)
- Amazon Bedrock model access for `amazon.titan-embed-text-v1` (and `amazon.nova-canvas-v1:0` if you regenerate images)
- ChatGPT with **Developer mode** (Pro, Plus, Business, Enterprise, or Education) — [docs](https://developers.openai.com/api/docs/guides/developer-mode/)

No Docker/Finch is required — the CLI builds a CodeZip artifact from `mcp_server/pyproject.toml`. The CLI handles the CDK bootstrap for you on first deploy.

## 1. Deploy

Set your deployment target, then deploy. Edit `agentcore/aws-targets.json` and replace the placeholder `account` with your 12-digit AWS account ID (keep the region on one that offers `amazon.titan-embed-text-v1`, e.g. `us-east-1`):

```json
[
  {
    "name": "default",
    "account": "123456789012",
    "region": "us-east-1"
  }
]
```

Then deploy from the repo root:

```bash
npx -y @aws/agentcore@0.31.1 deploy -y
```

`-y` auto-approves the CDK changes. The CLI synthesizes and deploys a single stack, `AgentCore-CoffeeDiscovery-default`, which creates (about 5–10 minutes):

| Resource | Purpose |
|---|---|
| AgentCore Runtime (`coffee_mcp`) | FastMCP server packaged from `mcp_server/` (CodeZip) |
| AgentCore Gateway (`coffee-runtime-noauth`) + target (`coffee-runtime-direct`) | MCP front door, outbound IAM to the runtime |
| OpenSearch Serverless collection `coffee-products` | semantic + keyword catalog search |
| DynamoDB `coffee-cart` | cart state |
| S3 bucket + CloudFront distribution | product image hosting |

Read the outputs you need (also visible with `agentcore status` and `agentcore fetch access`):

```
GatewayMcpUrl      = https://<id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp
OpenSearchEndpoint = https://<id>.<region>.aoss.amazonaws.com
```

`GatewayMcpUrl` is what you paste into ChatGPT.

## 2. Load the catalog

From the repo root:

```bash
export OPENSEARCH_ENDPOINT=<OpenSearchEndpoint output>
uv run --with-requirements <(uv pip compile mcp_server/pyproject.toml) python3 scripts/setup_data.py
```

Or simply install the deps from `mcp_server/pyproject.toml` into your environment and run `python3 scripts/setup_data.py`.

`setup_data.py` is idempotent. It creates the `coffee-products` index (knn_vector, dim 1536), generates Titan embeddings for the 24 products in `data/products.json`, and upserts them by `product_id`. It reuses the image URLs already in `products.json`. If `OPENSEARCH_ENDPOINT` is unset, it reads the `OpenSearchEndpoint` output from the `AgentCore-CoffeeDiscovery-default` stack (override the stack name with `AGENTCORE_STACK_NAME`).

To regenerate product images with Nova Canvas, also export `S3_BUCKET` and `CLOUDFRONT_DOMAIN` (the `ProductImagesBucketName` / `ProductImagesCDNDomain` outputs) before running the script.

OpenSearch Serverless data-access policies are eventually consistent. If your first search returns no products, wait 2–3 minutes and retry.

## 3. Connect ChatGPT

1. ChatGPT → **Settings → Apps & Connectors → Advanced settings** → enable **Developer mode**
2. **Create** a connector:
   - **Name:** `Coffee Discovery`
   - **MCP Server URL:** the `GatewayMcpUrl` output
   - **Authentication:** **None**
3. Start a new chat → **+** → **Developer mode** → select **Coffee Discovery**

Try:

```
I want a fruity light roast coffee
Show me Ethiopian coffees under $20
Find something similar to that one but darker
add the Kenyan to my cart
show my cart
```

Tools appear prefixed with the Gateway target name (for example `coffee-runtime-direct___search_products_tool`). That is expected.

### Verify without ChatGPT

```bash
export GATEWAY_URL=<GatewayMcpUrl output>
curl -s -X POST "$GATEWAY_URL" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

You should see the eight coffee tools (prefixed `coffee-runtime-direct___`) plus AgentCore's built-in `x_amz_bedrock_agentcore_search`.

## Local development

Run the MCP server locally with hot-reload (no container runtime needed):

```bash
npx -y @aws/agentcore@0.31.1 dev
```

## Adding authentication

AgentCore Gateway inbound authorization is configured gateway-wide as one of `NONE`, `AWS_IAM`, or `CUSTOM_JWT`. This deployment uses `NONE`.

To require per-user login, switch the Gateway's inbound authorizer to `CUSTOM_JWT`:

```bash
npx -y @aws/agentcore@0.31.1 add gateway --name coffee-runtime-noauth \
  --protocol-type MCP --authorizer-type CUSTOM_JWT \
  --discovery-url https://<issuer>/.well-known/openid-configuration
```

Point it at an OAuth 2.1 identity provider that advertises PKCE in its discovery document (`code_challenge_methods_supported: ["S256"]`), such as Okta, Auth0, Microsoft Entra ID, or Keycloak. ChatGPT enforces this during connector setup. Amazon Cognito's hosted OIDC discovery document does not advertise PKCE and cannot be edited, so raw Cognito cannot be the inbound issuer for ChatGPT. The Gateway→Runtime hop is unaffected — it uses the Gateway's IAM role (SigV4), not a user token.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `tools/list` returns empty or 4xx | Gateway target still provisioning. Wait 1–2 minutes. |
| "No products found" | Data-access policy still propagating, or `setup_data.py` not run. |
| Tiles render but images are blank | `CLOUDFRONT_DOMAIN` seen by the runtime doesn't match the CloudFront CDN domain. Check the widget CSP `resource_domains` in `mcp_server/server.py`. |
| ChatGPT rejects the connector | Authentication must be **None** for this stack. |
| Cart doesn't persist | Check the `coffee-cart` DynamoDB table and the runtime role's DynamoDB permissions. |

Runtime logs are in CloudWatch under `/aws/bedrock-agentcore/runtimes/<runtime-id>` (also `agentcore logs`).

## Updating the catalog

Edit `data/products.json` (schema below) and re-run `python3 scripts/setup_data.py`. Existing products are updated by `product_id`; new ones are added. Removed products stay in OpenSearch until deleted manually.

```json
{
  "product_id": "ethiopian-yirgacheffe-light",
  "name": "Ethiopian Yirgacheffe",
  "description": "Bright, floral light roast with jasmine and bergamot.",
  "origin": "Ethiopia",
  "roast_level": "light",
  "flavor_profile": ["floral", "fruity", "citrus"],
  "price": 18.99,
  "image_url": "https://<cdn>/images/ethiopian-yirgacheffe-light.png"
}
```

## Cleanup

Tear down everything the CLI manages: remove all resources from the project spec, then deploy the now-empty spec so the CLI deletes the stack.

```bash
npx -y @aws/agentcore@0.31.1 remove all
npx -y @aws/agentcore@0.31.1 deploy -y
```

The OpenSearch collection, DynamoDB table, runtime, and gateway are deleted. The image **S3 bucket is retained by design** (`RETAIN`), so empty and delete it manually once you no longer need the images:

```bash
aws s3 rm "s3://<ProductImagesBucketName output>" --recursive
aws s3 rb "s3://<ProductImagesBucketName output>"
```

## Project structure

```
.
├── AGENTS.md                          # AgentCore project context for AI assistants
├── data/products.json                 # 24-product coffee catalog
├── agentcore/
│   ├── agentcore.json                 # Project spec: coffee_mcp runtime + coffee-runtime-noauth gateway
│   ├── aws-targets.json               # Deployment target (account + region) — placeholder; set yours
│   └── cdk/
│       └── lib/cdk-stack.ts           # Customized stack: OpenSearch, DynamoDB, S3+CloudFront,
│                                      #   runtime env/IAM, hand-written gateway→runtime target
├── mcp_server/
│   ├── pyproject.toml                 # CodeZip dependency spec (pinned)
│   ├── server.py                      # FastMCP server, tools, widget resources
│   ├── tools.py                       # search / details / refine
│   ├── cart_tools.py, cart_manager.py, cart_repository.py
│   ├── opensearch_client.py, embeddings.py, preference_parser.py
│   ├── web_component.html             # product tiles widget
│   └── cart_component.html            # cart widget
└── scripts/
    ├── setup_data.py                  # create index + embed + load (idempotent)
    ├── generate_all_images.py         # optional: Nova Canvas images → S3
    └── image_generator.py, upload_to_s3.py
```

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file.

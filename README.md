# Host a ChatGPT App MCP Server on Amazon Bedrock AgentCore

A ChatGPT App that helps users discover and buy coffee beans through conversation. The app is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server built with the [ChatGPT Apps SDK](https://platform.openai.com/docs/guides/apps), hosted on **Amazon Bedrock AgentCore Runtime** and fronted by an **AgentCore Gateway**. ChatGPT connects to a single Gateway URL with no authentication configuration.

This is the companion code for the AWS blog post *Build ChatGPT Apps with MCP Servers and AWS Infrastructure, Part 2*. Part 1 ([blog](https://aws.amazon.com/blogs/industries/build-chatgpt-apps-with-mcp-servers-and-aws-infrastructure/)) hosted the same MCP server on AWS Lambda + API Gateway; that code is preserved at the [`part-1-lambda`](../../tree/part-1-lambda) tag.

> **⚠️ Security notice:** This is a demo, not a production reference. The Gateway accepts unauthenticated requests and OpenSearch Serverless uses public network access. See [Adding authentication](#adding-authentication) before exposing anything real.

## What the app does

- Search a coffee catalog in natural language ("fruity light roast under $20")
- Render results as interactive product tiles inside ChatGPT
- Refine by origin, roast level, flavor profile, price, or similarity
- Add items to a persistent shopping cart and view/update it

## Architecture

```
ChatGPT ──(MCP, no auth)──▶ AgentCore Gateway ──(Cognito M2M OAuth)──▶ AgentCore Runtime
                                                                          │  mcp_server/
                                          ┌───────────────────────────────┼──────────────────┐
                                          ▼                               ▼                  ▼
                                   OpenSearch Serverless           DynamoDB (coffee-cart)   Bedrock Titan
                                   hybrid + vector search          cart state               embeddings

Product images: S3 ──▶ CloudFront (ImageHostingStack)
```

- **AgentCore Runtime** hosts the FastMCP server (`mcp_server/`) as a streamable-HTTP MCP endpoint.
- **AgentCore Gateway** exposes the runtime to ChatGPT. Inbound auth is `NONE`; the Gateway authenticates to the runtime with a Cognito machine-to-machine client that the stack creates and ChatGPT never sees.
- **OpenSearch Serverless** stores the catalog with Titan embeddings for hybrid (keyword + semantic) search.
- **DynamoDB** persists cart state across the conversation.
- **S3 + CloudFront** serve the product images referenced by the widgets.

## Prerequisites

- AWS CLI with credentials (`aws sts get-caller-identity` works)
- AWS CDK bootstrapped in the target account/region (`npx aws-cdk bootstrap`)
- Python 3.11+ and [`uv`](https://github.com/astral-sh/uv)
- Docker or Finch running — CDK bundles the runtime for `linux/arm64`. For Finch: `export CDK_DOCKER=finch` and `finch vm start`
- Amazon Bedrock model access for `amazon.titan-embed-text-v1` (and `amazon.nova-canvas-v1:0` if you regenerate images)
- ChatGPT with **Developer mode** (Pro, Plus, Business, Enterprise, or Education) — [docs](https://developers.openai.com/api/docs/guides/developer-mode/)

## 1. Deploy

```bash
cd infrastructure
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

export CDK_DOCKER=finch   # only if using Finch
npx aws-cdk deploy --all --require-approval never
```

This deploys two stacks (about 5–10 minutes):

| Stack | Creates |
|---|---|
| `ImageHostingStack` | S3 bucket + CloudFront distribution for product images |
| `AgentCoreStack` | AgentCore Runtime (bundled from `mcp_server/`), AgentCore Gateway + target, OpenSearch Serverless collection, DynamoDB `coffee-cart` table, internal Cognito M2M pool |

Save these outputs:

```
AgentCoreStack.GatewayMcpUrl      = https://<id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp
AgentCoreStack.OpenSearchEndpoint = https://<id>.<region>.aoss.amazonaws.com
```

`GatewayMcpUrl` is what you paste into ChatGPT.

## 2. Load the catalog

From the repo root:

```bash
export OPENSEARCH_ENDPOINT=<AgentCoreStack.OpenSearchEndpoint>
python3 scripts/setup_data.py
```

`setup_data.py` is idempotent. It creates the `coffee-products` index (knn_vector, dim 1536), generates Titan embeddings for the 24 products in `data/products.json`, and upserts them by `product_id`. It reuses the image URLs already in `products.json`.

To regenerate product images with Nova Canvas, also export `S3_BUCKET` and `CLOUDFRONT_DOMAIN` from the `ImageHostingStack` outputs before running the script.

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
export GATEWAY_URL=<AgentCoreStack.GatewayMcpUrl>
curl -s -X POST "$GATEWAY_URL" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

You should see the eight coffee tools plus AgentCore's built-in `x_amz_bedrock_agentcore_search`.

## Adding authentication

AgentCore Gateway inbound authorization is configured gateway-wide as one of `NONE`, `JWT` (OIDC), or `IAM`. This deployment uses `NONE`.

To require per-user login, switch the Gateway's inbound authorizer to `JWT` and point it at an OAuth 2.1 identity provider that advertises PKCE in its discovery document (`code_challenge_methods_supported: ["S256"]`), such as Okta, Auth0, Microsoft Entra ID, or Keycloak. ChatGPT enforces this during connector setup. Amazon Cognito's hosted OIDC discovery document does not advertise PKCE and cannot be edited, so raw Cognito cannot be the inbound issuer for ChatGPT. The internal Cognito pool used for the Gateway→Runtime hop is unaffected.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| CDK bundling fails | Docker/Finch not running. Set `CDK_DOCKER=finch` if using Finch. |
| `tools/list` returns empty or 4xx | Gateway target still provisioning. Wait 1–2 minutes. |
| "No products found" | Data-access policy still propagating, or `setup_data.py` not run. |
| Tiles render but images are blank | `CLOUDFRONT_DOMAIN` seen by the runtime doesn't match the `ImageHostingStack` CDN domain. Check the widget CSP `resource_domains` in `mcp_server/server.py`. |
| ChatGPT rejects the connector | Authentication must be **None** for this stack. |
| Cart doesn't persist | Check the `coffee-cart` DynamoDB table and the runtime role's DynamoDB permissions. |

Runtime logs are in CloudWatch under `/aws/bedrock-agentcore/runtimes/<runtime-id>`.

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

```bash
cd infrastructure
npx aws-cdk destroy --all
```

The OpenSearch collection, DynamoDB table, runtime, and gateway are deleted. The image S3 bucket is retained by design; empty and delete it manually if you no longer need it.

## Project structure

```
.
├── data/products.json                 # 24-product coffee catalog
├── infrastructure/
│   ├── app.py                         # CDK app: ImageHostingStack + AgentCoreStack
│   └── stacks/
│       ├── agentcore_stack.py         # Runtime, Gateway, OpenSearch, DynamoDB, Cognito M2M
│       └── image_hosting_stack.py     # S3 + CloudFront
├── mcp_server/
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

# Host a ChatGPT App MCP Server on Amazon Bedrock AgentCore

A ChatGPT App that helps users discover and buy coffee beans through conversation. The app is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server built with the [ChatGPT Apps SDK](https://platform.openai.com/docs/guides/apps), hosted on **Amazon Bedrock AgentCore Runtime** and fronted by an **AgentCore Gateway**. ChatGPT connects to a single Gateway URL with no authentication configuration.

The whole backend lifecycle runs through the **AgentCore CLI** (`@aws/agentcore`): you add the runtime and gateway with two `agentcore add` commands, then `agentcore deploy` bootstraps CDK, packages the server, and deploys. No Docker or Finch is required — the runtime is packaged as a CodeZip artifact.

This is the companion code for the AWS blog post *Build ChatGPT Apps with MCP Servers and AWS Infrastructure, Part 2*. Part 1 ([blog](https://aws.amazon.com/blogs/industries/build-chatgpt-apps-with-mcp-servers-and-aws-infrastructure/)) hosted the same MCP server on AWS Lambda + API Gateway; that code is preserved at the [`part-1-lambda`](../../tree/part-1-lambda) tag.

> **⚠️ Security notice:** This is a demo, not a production reference. The Gateway accepts unauthenticated requests and OpenSearch Serverless uses public network access. See [Adding authentication](#adding-authentication) before exposing anything real.

## Why the AgentCore CLI

The [`main`](../../tree/main) branch provisions this same backend with hand-written Python CDK. This branch does the same work through the AgentCore CLI:

| | Hand-written CDK (`main`) | AgentCore CLI (this branch) |
|---|---|---|
| Tooling | Python venv, CDK CLI, Docker/Finch VM running | Node 20+ |
| CDK bootstrap | Run `npx aws-cdk bootstrap` yourself | `agentcore deploy` does it on first run |
| Package the MCP server | Docker arm64 bundling container | CodeZip built with `uv`, no Docker |
| Runtime | Hand-written CDK | `agentcore add agent` |
| Gateway + auth to the runtime | Gateway, Cognito pool, domain, resource server, M2M client, OAuth credential provider | `agentcore add gateway`; the gateway calls the runtime with its own IAM role (no Cognito) |
| Preview / deploy / inspect / logs / teardown | `cdk diff`, `cdk deploy`, CloudFormation console, CloudWatch, `cdk destroy` | `agentcore deploy --diff`, `deploy`, `status`, `logs`, `remove all` |
| Infrastructure code | 572 lines of Python CDK in 3 files (`git show main:infrastructure/...` — 406 + 133 + 33) | 2 CLI commands for the runtime + gateway; 310 lines of CDK for the app's own data layer |

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
- Node.js 20+ (for the AgentCore CLI)
- Python 3.11+ and [`uv`](https://github.com/astral-sh/uv) (for the data-setup scripts)
- Amazon Bedrock model access for `amazon.titan-embed-text-v1` (and `amazon.nova-canvas-v1:0` if you regenerate images)
- ChatGPT with **Developer mode** (Pro, Plus, Business, Enterprise, or Education) — [docs](https://developers.openai.com/api/docs/guides/developer-mode/)

No Docker/Finch is required — the CLI builds a CodeZip artifact from `mcp_server/pyproject.toml`. The CLI handles the CDK bootstrap for you on first deploy.

## 0. Install the CLI

```bash
npm install -g @aws/agentcore@0.31.1
agentcore --version
```

If you'd rather not install globally, alias the one-off runner instead and use `agentcore` the same way everywhere below:

```bash
alias agentcore='npx -y @aws/agentcore@0.31.1'
```

## 1. Point the project at your account

The repo is already an AgentCore project. It was created with `agentcore create --project-name CoffeeDiscovery --no-agent`, and the data layer was added in `agentcore/cdk/lib/cdk-stack.ts`. The committed `agentcore/agentcore.json` has **no runtime and no gateway** yet — you add those in the next two steps.

Edit `agentcore/aws-targets.json` and replace the placeholder account with your 12-digit AWS account ID. Use a region that offers `amazon.titan-embed-text-v1`, such as `us-east-1`:

```json
[
  {
    "name": "default",
    "account": "123456789012",
    "region": "us-east-1"
  }
]
```

## 2. Add the MCP server as a runtime

```bash
agentcore add agent \
  --name coffee_mcp \
  --type byo \
  --language Python \
  --protocol MCP \
  --code-location ./mcp_server \
  --entrypoint server.py
```

This registers the existing FastMCP server (`mcp_server/`) as an AgentCore Runtime. Open `agentcore/agentcore.json` to see the runtime block the CLI wrote — a `coffee_mcp` runtime with `build: CodeZip`, `protocol: MCP`, and OpenTelemetry off.

`agentcore add agent` has no runtime-version flag; it defaults to `PYTHON_3_14`. That is what this walkthrough uses. If the server fails to start on 3.14 (packaging, import, or runtime errors), set `"runtimeVersion": "PYTHON_3_11"` in the runtime block of `agentcore/agentcore.json`, re-run `agentcore validate`, and redeploy — `mcp_server/pyproject.toml` requires Python 3.11+.

## 3. Add the gateway ChatGPT connects to

```bash
agentcore add gateway \
  --name coffee-runtime-noauth \
  --protocol-type MCP \
  --authorizer-type NONE
```

Creates an MCP gateway with no inbound auth, which is what ChatGPT's "Authentication: None" connector expects. Keep the names `coffee_mcp` and `coffee-runtime-noauth`: `cdk-stack.ts` looks them up by name to attach the gateway-to-runtime target and wire the data layer. If either name is missing, `agentcore deploy` prints a warning and skips the coffee backend instead of failing.

## 4. Validate and preview

```bash
agentcore validate          # checks agentcore.json against the schema
agentcore deploy --diff     # shows the CDK diff without deploying
```

The diff now includes the runtime, the gateway, and the coffee data layer (OpenSearch, DynamoDB, S3 + CloudFront).

## 5. Deploy

```bash
agentcore deploy -y
```

In one command the CLI checks the CDK bootstrap and runs it if needed, packages `mcp_server/` for arm64 with `uv` (no Docker), synthesizes the stack, and deploys `AgentCore-CoffeeDiscovery-default` (about 10 minutes — roughly 9m50s on the test run). It creates:

| Resource | Purpose |
|---|---|
| AgentCore Runtime (`coffee_mcp`) | FastMCP server packaged from `mcp_server/` (CodeZip) |
| AgentCore Gateway (`coffee-runtime-noauth`) + target (`coffee-runtime-direct`) | MCP front door, outbound IAM to the runtime |
| OpenSearch Serverless collection `coffee-products` | semantic + keyword catalog search |
| DynamoDB `coffee-cart` | cart state |
| S3 bucket + CloudFront distribution | product image hosting |

> **Account-wide side effect:** `agentcore deploy` also turns on [CloudWatch Transaction Search](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Transaction-Search.html) for the region (deploy prints `Transaction search enabled`). It sends X-Ray traces to CloudWatch Logs and indexes 100% of spans, which applies to every workload in the account and region, not just this stack. This sample doesn't need it; step 12 shows how to turn it back off.

## 6. See what you deployed

```bash
agentcore status
agentcore fetch access --name coffee-runtime-noauth --type gateway
```

`agentcore status` lists the deployed runtime and gateway; `fetch access` prints the gateway's MCP URL — what you paste into ChatGPT.

If `fetch access` does not print a URL for a no-inbound-auth gateway, read the `GatewayMcpUrl` stack output instead:

```bash
aws cloudformation describe-stacks \
  --stack-name AgentCore-CoffeeDiscovery-default \
  --query "Stacks[0].Outputs[?OutputKey=='GatewayMcpUrl'].OutputValue" \
  --output text
```

## 7. Load the catalog

```bash
uv run --with-requirements <(uv pip compile mcp_server/pyproject.toml) python3 scripts/setup_data.py
```

The script reads the `OpenSearchEndpoint` output from the stack automatically (override the stack name with `AGENTCORE_STACK_NAME`, or set `OPENSEARCH_ENDPOINT` directly). It creates the `coffee-products` index (knn_vector, dim 1536), generates Titan embeddings for the 24 products in `data/products.json`, and upserts them by `product_id`. It is idempotent.

OpenSearch Serverless data-access policies are eventually consistent. If your first search returns nothing, wait 2–3 minutes for the policy to take effect and retry.

To regenerate product images with Nova Canvas, also export `S3_BUCKET` and `CLOUDFRONT_DOMAIN` (the `ProductImagesBucketName` / `ProductImagesCDNDomain` outputs) before running the script.

## 8. Call a tool on the deployed runtime

```bash
agentcore invoke call-tool --tool search_products_tool \
  --input '{"preferences": "fruity light roast"}'
```

Calls the runtime directly with your AWS credentials, so you can confirm the server works before ChatGPT is involved. Tool names have no prefix here; through the gateway they appear as `coffee-runtime-direct___search_products_tool`.

## 9. Connect ChatGPT

1. ChatGPT → **Settings → Apps & Connectors → Advanced settings** → enable **Developer mode**
2. **Create** a connector:
   - **Name:** `Coffee Discovery`
   - **MCP Server URL:** the gateway URL from step 6
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

Tools appear prefixed with the Gateway target name (for example `coffee-runtime-direct___search_products_tool`). That is expected. `cdk-stack.ts` passes the same prefix to the runtime as `TOOL_NAME_PREFIX`, and the server returns it to the widgets (`tool_prefix`) so their buttons call the prefixed names.

### Verify without ChatGPT

```bash
export GATEWAY_URL=<gateway URL from step 6>
curl -s -X POST "$GATEWAY_URL" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

You should see the eight coffee tools (prefixed `coffee-runtime-direct___`) plus AgentCore's built-in `x_amz_bedrock_agentcore_search`.

## 10. Watch it run

```bash
agentcore logs --runtime coffee_mcp                       # follow live
agentcore logs --runtime coffee_mcp --since 30m --level error
```

Chat with the app in ChatGPT and watch the tool calls show up in the logs.

## 11. Iterate locally

`agentcore dev` runs the FastMCP server on your machine (it builds a local Python 3.11 virtualenv under `mcp_server/.venv`). It loads `agentcore/.env.local` if that file exists and also inherits your exported shell environment. The deployed runtime gets `OPENSEARCH_ENDPOINT`, `CLOUDFRONT_DOMAIN`, and the cart table name injected by `cdk-stack.ts`; locally you supply them yourself — either export them (shown below) or put them in `agentcore/.env.local`. Read them from the stack outputs first:

```bash
STACK=AgentCore-CoffeeDiscovery-default
export AWS_REGION=us-east-1
export OPENSEARCH_ENDPOINT=$(aws cloudformation describe-stacks --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='OpenSearchEndpoint'].OutputValue" --output text)
export CLOUDFRONT_DOMAIN=https://$(aws cloudformation describe-stacks --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='ProductImagesCDNDomain'].OutputValue" --output text)
# The cart table is read from DYNAMODB_CART_TABLE; it defaults to coffee-cart (the deployed
# table name), so you only need to export it if you renamed the table.
export DYNAMODB_CART_TABLE=coffee-cart
```

```bash
# terminal 1
agentcore dev --runtime coffee_mcp --logs

# terminal 2
agentcore dev list-tools
agentcore dev call-tool --tool get_product_details_tool \
  --input '{"product_id": "ethiopian-yirgacheffe-light"}'
agentcore dev call-tool --tool add_to_cart \
  --input '{"product_id": "ethiopian-yirgacheffe-light", "quantity": 2}'
agentcore dev call-tool --tool view_cart --input '{}'
agentcore dev call-tool --tool clear_cart --input '{}'
```

`agentcore dev list-tools` lists the eight tools. All of them run locally against the deployed AWS resources using **your** credentials:

- The cart tools (`add_to_cart`, `view_cart`, `update_cart_quantity`, `remove_from_cart`, `clear_cart`) store the cart in the deployed DynamoDB table and look up product details in OpenSearch.
- The OpenSearch-backed tools (`search_products_tool`, `get_product_details_tool`, `refine_preferences_tool`) sign OpenSearch Serverless requests as your IAM principal. These work locally as long as your principal has data-plane access to the `coffee-products` collection — which the account root grant in the `coffee-products-access` data-access policy already provides (it is the same access that lets `scripts/setup_data.py` in step 7 write the catalog as you).

> **If OpenSearch calls return `AuthenticationException(401)`:** the collection's network policy
> is blocking the request. This hits the deployed runtime and `scripts/setup_data.py` too, not
> just `agentcore dev`. See the 401 row in [Troubleshooting](#troubleshooting).

Edit `mcp_server/*.py`; the dev server reloads. Ship the change with `agentcore deploy -y`.

## 12. Clean up

```bash
agentcore remove all --dry-run   # preview what will be removed
agentcore remove all -y          # clear the runtime + gateway from the project spec
agentcore deploy -y              # deploy the now-empty spec, which deletes the stack
```

Then empty and delete the image bucket, which is kept on purpose (`RETAIN`):

```bash
aws s3 rm "s3://<ProductImagesBucketName>" --recursive
aws s3 rb "s3://<ProductImagesBucketName>"
```

If Transaction Search was off before you deployed (see the note in step 5), turn it back off. Skip this if other workloads in the account rely on it.

```bash
aws xray update-indexing-rule --name Default \
  --rule '{"Probabilistic":{"DesiredSamplingPercentage":1}}'
aws xray update-trace-segment-destination --destination XRay
aws logs delete-resource-policy --policy-name TransactionSearchXRayAccess
aws logs delete-log-group --log-group-name aws/spans
aws logs delete-log-group --log-group-name /aws/application-signals/data
```

After cleanup, `agentcore.json` is back to its committed state: no runtime, no gateway. Steps 2–5 deploy it again.

## Adding authentication

AgentCore Gateway inbound authorization is configured gateway-wide as one of `NONE`, `AWS_IAM`, or `CUSTOM_JWT`. This deployment uses `NONE`.

To require per-user login, switch the Gateway's inbound authorizer to `CUSTOM_JWT`:

```bash
agentcore add gateway --name coffee-runtime-noauth \
  --protocol-type MCP --authorizer-type CUSTOM_JWT \
  --discovery-url https://<issuer>/.well-known/openid-configuration
```

Point it at an OAuth 2.1 identity provider that advertises PKCE in its discovery document (`code_challenge_methods_supported: ["S256"]`), such as Okta, Auth0, Microsoft Entra ID, or Keycloak. ChatGPT enforces this during connector setup. Amazon Cognito's hosted OIDC discovery document does not advertise PKCE and cannot be edited, so raw Cognito cannot be the inbound issuer for ChatGPT. The Gateway→Runtime hop is unaffected — it uses the Gateway's IAM role (SigV4), not a user token.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `agentcore deploy` warns "Coffee Discovery backend skipped" | The `coffee_mcp` runtime or `coffee-runtime-noauth` gateway is missing. Run the `agentcore add agent` / `agentcore add gateway` commands from steps 2–3. |
| `tools/list` returns empty or 4xx | Gateway target still provisioning. Wait 1–2 minutes. |
| "No products found" | `setup_data.py` (step 7) not run yet, or the index/data-access policy is still propagating — retry after 2–3 minutes. |
| `AuthenticationException(401)` on OpenSearch calls (search, product details, or the cart), from the deployed runtime, `agentcore dev`, or `setup_data.py` | The collection's network policy is blocking the request (`x-aoss-response-hint: X01:network-policy-deny`). Signing or data-access problems return 403 instead, so adding yourself to the data-access policy won't help. Run `aws opensearchserverless get-security-policy --type network --name coffee-products-net --query 'securityPolicyDetail.policy[0].AllowFromPublic'`. If it prints `false` and you didn't change it, automated security remediation in your account most likely turned off the collection's public access. Don't turn it back on where private access is enforced: the sample needs a VPC-only network policy to run there, which it doesn't include yet. |
| Tiles render but images are blank | `CLOUDFRONT_DOMAIN` seen by the runtime doesn't match the CloudFront CDN domain. Check the widget CSP `resource_domains` in `mcp_server/server.py`. |
| Widget buttons (Add to Cart, +/−, Remove) show "Try Again" while typed prompts work | The widget called an unprefixed tool name, which the gateway rejects (`Unknown tool`). Redeploy (`agentcore deploy -y`) so the runtime has `TOOL_NAME_PREFIX`, then start a new chat so ChatGPT reloads the widget. If the runtime logs show `AuthenticationException(401)` instead, see the 401 row above. |
| ChatGPT rejects the connector | Authentication must be **None** for this stack. |
| Cart doesn't persist | Check the `coffee-cart` DynamoDB table and the runtime role's DynamoDB permissions. |

Runtime logs are in CloudWatch under `/aws/bedrock-agentcore/runtimes/<runtime-id>` (also `agentcore logs --runtime coffee_mcp`).

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

## What's still hand-written, and why

310 lines in `agentcore/cdk/lib/cdk-stack.ts` (the `addCoffeeDiscoveryBackend` method) cover only what the CLI's config can't describe:

- **App data layer:** OpenSearch Serverless (collection + 3 policies), the DynamoDB `coffee-cart` table, and S3 + CloudFront for images.
- **Wiring:** the runtime's environment variables and IAM permissions for those resources, looked up by the runtime name `coffee_mcp`.
- **Gateway-to-runtime target (`coffee-runtime-direct`):** the CLI only offers OAuth or no auth for MCP targets, and it can't point a target at a runtime defined in the same project. So the target, which uses the gateway's IAM role, is added in CDK.

If the runtime or gateway isn't in `agentcore.json` yet (the committed starting state), this whole block is skipped and `agentcore deploy` prints a message telling you to add them — nothing is provisioned until both exist.

## Project structure

```
.
├── AGENTS.md                          # AgentCore project context for AI assistants
├── data/products.json                 # 24-product coffee catalog
├── agentcore/
│   ├── agentcore.json                 # Project spec: empty by default (no runtime/gateway
│   │                                  #   until you run the `agentcore add` commands)
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

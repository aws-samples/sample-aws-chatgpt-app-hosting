# Contributing to Coffee Discovery ChatGPT App

## Getting Started

### Prerequisites

- **AWS Account** with permissions for:
  - CDK deployments
  - OpenSearch Serverless
  - Cognito
  - Lambda
  - API Gateway
  - Bedrock (Titan Embeddings and Nova Canvas)
- **AWS CLI** configured with credentials
- **Node.js** 18+ and npm
- **Python** 3.11+
- **uv** (Python package manager)
- **Docker** or **Finch** (for CDK asset bundling)

### Initial Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd coffee-discovery-chatgpt-app
   ```

2. **Install CDK dependencies**
   ```bash
   cd infrastructure
   npm install
   cd ..
   ```

3. **Install Python dependencies**
   ```bash
   uv pip install --system opensearch-py requests-aws4auth boto3
   ```

4. **Configure AWS credentials**
   ```bash
   aws configure
   # Or use your organization's SSO/authentication method
   ```

5. **Bootstrap CDK** (first time only)
   ```bash
   cd infrastructure
   npx aws-cdk bootstrap
   cd ..
   ```

## Development Workflow

### Deploying Infrastructure

```bash
cd infrastructure
npx cdk deploy
cd ..
```

**Important**: Save the CDK outputs! You'll need:
- `OpenSearchEndpoint`
- `CognitoUserPoolId`
- `CognitoClientId`
- `CognitoDiscoveryUrl`
- `MCPServerURL`

### Loading Product Data

After deployment, load the product catalog:

```bash
# Set the OpenSearch endpoint from CDK outputs
export OPENSEARCH_ENDPOINT=<OpenSearchEndpoint from CDK outputs>

# Option 1: Full script with embeddings (recommended)
python3 scripts/load_catalog.py

# Option 2: Simple script (if Option 1 fails with 403)
python3 scripts/simple_load.py
```

**Note**: If you encounter 403 errors, wait 2-5 minutes for OpenSearch policies to propagate, then retry.

### Creating Test Users

```bash
export USER_POOL_ID=<CognitoUserPoolId from CDK outputs>
export USERNAME=<your-username>
export PASSWORD=<secure-password>

aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username $USERNAME \
  --temporary-password TempPass123! \
  --message-action SUPPRESS

aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username $USERNAME \
  --password $PASSWORD \
  --permanent
```

## Important Notes for Contributors

### No Hardcoded Credentials

- **Never commit** AWS credentials, tokens, or API keys
- Use environment variables for configuration
- Personal token files (`cognito_tokens*.txt`) are gitignored

### OpenSearch Serverless Quirks

OpenSearch Serverless has some unique behaviors:

1. **Policy Propagation**: Access policies take 2-5 minutes to propagate
2. **Eventually Consistent**: Wait after policy changes before testing
3. **Use Simple Scripts**: If `load_catalog.py` fails with 403, try `simple_load.py`

See `OPENSEARCH-QUICKREF.md` for troubleshooting.

### AWS CLI Pager

When running AWS CLI commands in scripts, always disable the pager:

```bash
export AWS_PAGER=""
```

Otherwise commands will hang waiting for user input.

### Testing Changes

1. **Test locally** before committing
2. **Run CDK diff** to see infrastructure changes:
   ```bash
   cd infrastructure
   npx cdk diff
   ```
3. **Test data loading** after infrastructure changes
4. **Verify in ChatGPT** that the connector still works

## Project Structure

```
.
├── infrastructure/          # CDK infrastructure code
│   ├── stacks/             # CDK stack definitions
│   └── app.py              # CDK app entry point
├── lambda/                 # Lambda function code (bundled)
├── mcp_server/            # MCP server implementation
│   ├── mcp_handler.py     # Lambda handler
│   ├── opensearch_client.py
│   ├── embeddings.py
│   └── web_component_simple.html
├── scripts/               # Utility scripts
│   ├── load_catalog.py    # Full data loader
│   ├── simple_load.py     # Simple data loader
│   ├── image_generator.py # AI image generation
│   └── test_image_generator.py
├── data/                  # Product catalog data
│   └── products.json
└── .kiro/                 # Kiro IDE configuration
    ├── specs/             # Feature specifications
    └── steering/          # Agent steering rules
```

## Common Tasks

### Adding New Products

1. Edit `data/products.json`
2. Run the data loader:
   ```bash
   export OPENSEARCH_ENDPOINT=<your-endpoint>
   python3 scripts/load_catalog.py
   ```

### Updating Lambda Code

1. Make changes in `mcp_server/` or `lambda/`
2. Deploy:
   ```bash
   cd infrastructure
   npx cdk deploy
   ```

### Regenerating AI Images

```bash
export OPENSEARCH_ENDPOINT=<your-endpoint>
python3 scripts/load_catalog.py --regenerate-images
```

### Updating Access Policies

If you need to modify OpenSearch access policies:

1. Edit `infrastructure/stacks/coffee_discovery_stack.py`
2. Deploy changes:
   ```bash
   cd infrastructure
   npx cdk deploy
   ```
3. **Wait 2-5 minutes** for propagation
4. Test with simple script:
   ```bash
   python3 scripts/simple_load.py
   ```

## Troubleshooting

### 403 Forbidden Errors

See `OPENSEARCH-QUICKREF.md` for detailed troubleshooting.

Quick fixes:
1. Wait 2-5 minutes after policy changes
2. Verify credentials: `aws sts get-caller-identity`
3. Try `simple_load.py` instead of `load_catalog.py`
4. Set `export AWS_PAGER=""`

### CDK Deployment Fails

- Ensure you're in the correct AWS account
- Check you have necessary permissions
- Verify Docker/Finch is running (for Lambda bundling)

### Image Generation Slow

- Normal: ~3-5 seconds per image
- Use `--skip-images` to bypass image generation
- Check Bedrock quotas if consistently failing

## Code Style

- **Python**: Follow PEP 8
- **TypeScript/CDK**: Use CDK best practices
- **Comments**: Explain why, not what
- **Documentation**: Update README when adding features

## Submitting Changes

1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Update documentation
5. Submit a pull request with:
   - Clear description of changes
   - Any new environment variables needed
   - Testing steps performed

## Getting Help

- Check `README.md` for setup instructions
- See `OPENSEARCH-QUICKREF.md` for OpenSearch issues
- Review `.kiro/steering/opensearch-troubleshooting.md` for detailed guides
- Check `.kiro/specs/` for feature specifications

## Security

- Never commit credentials or tokens
- Use IAM roles with least privilege
- Rotate Cognito user passwords regularly
- Review CloudWatch logs for suspicious activity

## License

[Your License Here]

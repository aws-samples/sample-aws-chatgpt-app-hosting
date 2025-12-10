# Setup Guide

Complete step-by-step guide to set up the Coffee Discovery ChatGPT App from scratch.

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] AWS Account with admin or sufficient permissions
- [ ] AWS CLI installed and configured
- [ ] Node.js 18+ installed
- [ ] Python 3.11+ installed
- [ ] uv installed
- [ ] Docker or Finch running
- [ ] Git installed

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url>
cd coffee-discovery-chatgpt-app
cd infrastructure && npm install && cd ..
uv pip install --system opensearch-py requests-aws4auth boto3

# 2. Configure AWS
aws configure

# 3. Bootstrap CDK (first time only)
cd infrastructure && npx aws-cdk bootstrap && cd ..

# 4. Deploy
cd infrastructure && npx cdk deploy --all --require-approval never && cd ..
# SAVE THE OUTPUTS!

# 5. Post-Deployment: Generate and Upload Images
# Get the values from CDK outputs
export OPENSEARCH_ENDPOINT=<from-cdk-outputs>
export CLOUDFRONT_DOMAIN=<from-cdk-outputs>
export S3_BUCKET=<from-cdk-outputs>

# Generate AI images and upload to S3 (takes ~2 minutes)
. infrastructure/.venv/bin/activate
python3 scripts/generate_all_images.py

# 6. Create OpenSearch Index with knn_vector mapping
python3 scripts/create_index.py

# 7. Load products into OpenSearch
python3 scripts/simple_load.py

# 7. Create test user
export USER_POOL_ID=<from-cdk-outputs>
aws cognito-idp admin-create-user --user-pool-id $USER_POOL_ID --username testuser --temporary-password TempPass123! --message-action SUPPRESS
aws cognito-idp admin-set-user-password --user-pool-id $USER_POOL_ID --username testuser --password TestPass123! --permanent

# 8. Configure in ChatGPT and test!
```

See full detailed instructions in README.md

## Troubleshooting

- **403 errors**: Wait 2-5 minutes after deployment, then retry. OpenSearch Serverless permissions are eventually consistent.
- **CLI hangs**: `export AWS_PAGER=""`
- **No data**: Verify with OpenSearch query (see README)
- **If load_catalog.py fails**: Use `python3 scripts/simple_load.py` as a fallback (creates index and loads data)

For more help, see:
- `OPENSEARCH-QUICKREF.md`
- `CONTRIBUTING.md`
- `.kiro/steering/opensearch-troubleshooting.md`

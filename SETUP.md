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
cd infrastructure && npx cdk deploy && cd ..
# SAVE THE OUTPUTS!

# 5. Wait for OpenSearch policies
sleep 120

# 6. Load data
export OPENSEARCH_ENDPOINT=<from-cdk-outputs>
python3 scripts/load_catalog.py

# 7. Create test user
export USER_POOL_ID=<from-cdk-outputs>
aws cognito-idp admin-create-user --user-pool-id $USER_POOL_ID --username testuser --temporary-password TempPass123! --message-action SUPPRESS
aws cognito-idp admin-set-user-password --user-pool-id $USER_POOL_ID --username testuser --password TestPass123! --permanent

# 8. Configure in ChatGPT and test!
```

See full detailed instructions in README.md

## Troubleshooting

- **403 errors**: Wait 2-5 minutes, try `python3 scripts/simple_load.py`
- **CLI hangs**: `export AWS_PAGER=""`
- **No data**: Verify with OpenSearch query (see README)

For more help, see:
- `OPENSEARCH-QUICKREF.md`
- `CONTRIBUTING.md`
- `.kiro/steering/opensearch-troubleshooting.md`

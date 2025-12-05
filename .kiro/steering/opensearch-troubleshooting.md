---
inclusion: manual
---

# OpenSearch Serverless Troubleshooting Guide

## Critical Lessons for OpenSearch Serverless

### 1. Policy Propagation Delays
**Problem**: Access policies can take 2-5+ minutes to propagate after updates.

**Solution**:
- Always wait at least 2 minutes after updating access policies
- Test with simple direct writes before running complex scripts
- Don't assume immediate policy application

**Code Pattern**:
```python
# After updating policy via AWS CLI or CDK
print("Waiting for policy propagation...")
time.sleep(120)  # Wait 2 minutes
```

### 2. AWS CLI Pager Issues
**Problem**: AWS CLI commands hang waiting for user to quit pager (less/more).

**Solution**: Always disable pager in scripts and automation:
```bash
export AWS_PAGER=""
aws opensearchserverless get-access-policy --name my-policy --type data
```

**In Python**:
```python
import os
os.environ['AWS_PAGER'] = ''
```

### 3. Simple Scripts Work Better
**Problem**: Complex scripts with multiple steps can fail mysteriously even when individual functions work.

**Solution**: When debugging OpenSearch write issues:
1. Create a minimal reproduction script
2. Test direct API calls first
3. Gradually add complexity

**Example Minimal Script**:
```python
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

endpoint = 'your-endpoint.aoss.amazonaws.com'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    'us-east-1',
    'aoss',
    session_token=credentials.token
)

client = OpenSearch(
    hosts=[{'host': endpoint, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)

# Test write
response = client.index(index='my-index', body={'test': 'value'})
print(f"Success: {response['_id']}")
```

### 4. Credential Refresh
**Problem**: Boto3 sessions can cache stale credentials.

**Solution**: For long-running scripts, recreate the OpenSearch client before critical operations:
```python
# Before indexing, recreate client with fresh credentials
client = setup_opensearch_client(endpoint, region)
```

### 5. Access Policy Principals
**Problem**: OpenSearch Serverless requires exact ARN matches or wildcards.

**Best Practice**:
```json
{
  "Principal": [
    "arn:aws:iam::ACCOUNT:root",
    "arn:aws:iam::ACCOUNT:role/RoleName",
    "arn:aws:sts::ACCOUNT:assumed-role/RoleName/*"
  ]
}
```

The wildcard `assumed-role/RoleName/*` is critical for covering all sessions.

### 6. Debugging Checklist

When OpenSearch writes fail with 403:

1. ✅ Verify credentials are valid: `aws sts get-caller-identity`
2. ✅ Check access policy includes your ARN: `aws opensearchserverless get-access-policy --name POLICY --type data`
3. ✅ Wait 2-5 minutes after policy changes
4. ✅ Test with minimal script (not full application)
5. ✅ Check if reads work: `client.search(index='my-index', body={'query': {'match_all': {}}})`
6. ✅ Try direct write: `client.index(index='my-index', body={'test': 'value'})`
7. ✅ If direct write works but script fails, simplify the script

### 7. Common Pitfalls

❌ **Don't**: Assume policy changes are immediate
✅ **Do**: Wait and verify with test writes

❌ **Don't**: Debug complex scripts when permissions fail
✅ **Do**: Create minimal reproduction first

❌ **Don't**: Forget to disable AWS_PAGER in automation
✅ **Do**: Set `export AWS_PAGER=""` at script start

❌ **Don't**: Use specific assumed-role ARNs without wildcards
✅ **Do**: Use `assumed-role/RoleName/*` pattern

### 8. Success Pattern

```python
#!/usr/bin/env python3
import os
import time
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Disable pager for any AWS CLI calls
os.environ['AWS_PAGER'] = ''

def create_client(endpoint, region):
    """Create OpenSearch client with fresh credentials"""
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        region,
        'aoss',
        session_token=credentials.token
    )
    
    return OpenSearch(
        hosts=[{'host': endpoint.replace('https://', ''), 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30
    )

def main():
    endpoint = os.environ['OPENSEARCH_ENDPOINT']
    region = 'us-east-1'
    
    # Create client
    client = create_client(endpoint, region)
    
    # Test connectivity
    try:
        response = client.index(
            index='my-index',
            body={'test': 'connectivity'},
            refresh=False
        )
        print(f"✅ Connected and can write: {response['_id']}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return
    
    # Do actual work...
    # For long operations, recreate client periodically
    client = create_client(endpoint, region)
    
    # Index data...

if __name__ == '__main__':
    main()
```

## When to Use This Guide

- Setting up new OpenSearch Serverless collections
- Debugging 403 Forbidden errors
- After updating access policies
- When scripts work locally but fail in automation
- When AWS CLI commands hang indefinitely

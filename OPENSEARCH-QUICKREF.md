# OpenSearch Serverless Quick Reference

## 🚨 Most Common Issues

### 403 Forbidden Errors
**Cause**: Policy propagation delay (2-5 minutes)  
**Fix**: Wait, then retry. Use `simple_load.py` if `load_catalog.py` fails.

### AWS CLI Hangs
**Cause**: Pager waiting for input  
**Fix**: `export AWS_PAGER=""`

### Script Works Locally, Fails in Automation
**Cause**: Credential caching or timing issues  
**Fix**: Use simpler script (`simple_load.py`) or recreate client before critical operations

## ✅ Quick Checks

```bash
# 1. Verify your identity
aws sts get-caller-identity

# 2. Check access policy (disable pager first!)
export AWS_PAGER=""
aws opensearchserverless get-access-policy \
  --name coffee-products-access \
  --type data

# 3. Test read access
python3 -c "
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import boto3

endpoint = 'YOUR-ENDPOINT.aoss.amazonaws.com'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, 'us-east-1', 'aoss', session_token=credentials.token)
client = OpenSearch(hosts=[{'host': endpoint, 'port': 443}], http_auth=awsauth, use_ssl=True, verify_certs=True, connection_class=RequestsHttpConnection)
print(client.search(index='coffee-products', body={'query': {'match_all': {}}, 'size': 1}))
"

# 4. Test write access
python3 -c "
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import boto3

endpoint = 'YOUR-ENDPOINT.aoss.amazonaws.com'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, 'us-east-1', 'aoss', session_token=credentials.token)
client = OpenSearch(hosts=[{'host': endpoint, 'port': 443}], http_auth=awsauth, use_ssl=True, verify_certs=True, connection_class=RequestsHttpConnection)
print(client.index(index='coffee-products', body={'test': 'value'}))
"
```

## 🔧 Loading Data

### Option 1: Full Script (with embeddings)
```bash
export OPENSEARCH_ENDPOINT="https://YOUR-ENDPOINT.aoss.amazonaws.com"
python3 scripts/load_catalog.py --skip-images
```

### Option 2: Simple Script (more reliable)
```bash
python3 scripts/simple_load.py
```

**Use simple_load.py when**:
- load_catalog.py fails with 403
- You just updated access policies
- You need a quick test
- Debugging permission issues

## 📋 Policy Update Workflow

```bash
# 1. Update policy
export AWS_PAGER=""
aws opensearchserverless update-access-policy \
  --name coffee-products-access \
  --type data \
  --policy-version CURRENT_VERSION \
  --policy '[{"Rules":[...], "Principal":[...]}]'

# 2. WAIT (critical!)
echo "Waiting for policy propagation..."
sleep 120

# 3. Test
python3 scripts/simple_load.py
```

## 🎯 Success Patterns

### Minimal Working Script Template
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

# Your operations here
response = client.index(index='my-index', body={'data': 'value'})
print(f"Success: {response['_id']}")
```

### Access Policy Template
```json
{
  "Rules": [
    {
      "ResourceType": "collection",
      "Resource": ["collection/my-collection"],
      "Permission": ["aoss:*"]
    },
    {
      "ResourceType": "index",
      "Resource": ["index/my-collection/*"],
      "Permission": ["aoss:*"]
    }
  ],
  "Principal": [
    "arn:aws:iam::ACCOUNT:root",
    "arn:aws:iam::ACCOUNT:role/RoleName",
    "arn:aws:sts::ACCOUNT:assumed-role/RoleName/*"
  ]
}
```

**Key**: The wildcard `assumed-role/RoleName/*` covers all sessions!

## 🐛 Debug Checklist

- [ ] `export AWS_PAGER=""`
- [ ] Wait 2-5 min after policy changes
- [ ] Verify identity matches policy
- [ ] Test read access first
- [ ] Test write with minimal script
- [ ] Check for credential expiration
- [ ] Try `simple_load.py` instead of `load_catalog.py`

## 📚 More Info

See `.kiro/steering/opensearch-troubleshooting.md` for detailed guide.

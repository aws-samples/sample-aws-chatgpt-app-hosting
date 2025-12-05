#!/usr/bin/env python3
"""Delete all products from OpenSearch"""

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Configuration
endpoint = 'fd8e6kvqc6bzfp19qou1.us-east-1.aoss.amazonaws.com'
region = 'us-east-1'
index_name = 'coffee-products'

# Set up OpenSearch client
print("Connecting to OpenSearch...")
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    region,
    'aoss',
    session_token=credentials.token
)

client = OpenSearch(
    hosts=[{'host': endpoint, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    timeout=30
)
print("✅ Connected")

# Delete the index
print(f'\nDeleting index "{index_name}"...')
try:
    if client.indices.exists(index=index_name):
        response = client.indices.delete(index=index_name)
        print(f'✅ Index deleted')
    else:
        print(f'⚠️  Index does not exist')
except Exception as e:
    print(f'✗ Error: {e}')

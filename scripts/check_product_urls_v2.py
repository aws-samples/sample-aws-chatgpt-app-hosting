#!/usr/bin/env python3
"""Check all product image URLs in OpenSearch using opensearchpy"""

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Configuration
endpoint = 'fd8e6kvqc6bzfp19qou1.us-east-1.aoss.amazonaws.com'
region = 'us-east-1'
index_name = 'coffee-products'

# Set up OpenSearch client
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

# Query all products
try:
    response = client.search(
        index=index_name,
        body={
            'size': 100,
            'query': {'match_all': {}}
        }
    )
    
    total = response['hits']['total']['value']
    print(f'Total products: {total}')
    print()
    
    unsplash_count = 0
    cloudfront_count = 0
    other_count = 0
    
    for hit in response['hits']['hits']:
        product = hit['_source']
        image_url = product.get('image_url', 'NO IMAGE URL')
        
        if 'unsplash.com' in image_url:
            unsplash_count += 1
            status = '✓ Unsplash'
        elif 'cloudfront.net' in image_url:
            cloudfront_count += 1
            status = '✗ CloudFront'
        else:
            other_count += 1
            status = '? Other'
        
        print(f'{status}: {product["name"]}')
        print(f'  URL: {image_url}')
    
    print()
    print(f'Summary:')
    print(f'  Unsplash URLs: {unsplash_count}')
    print(f'  CloudFront URLs: {cloudfront_count}')
    print(f'  Other URLs: {other_count}')
    
except Exception as e:
    print(f'Error: {e}')

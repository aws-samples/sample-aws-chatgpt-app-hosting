#!/usr/bin/env python3
"""Check all product image URLs in OpenSearch"""

import json
import requests
from requests_aws4auth import AWS4Auth
import boto3

# Get credentials
session = boto3.Session()
credentials = session.get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    session.region_name or 'us-east-1',
    'aoss',
    session_token=credentials.token
)

# Query all products
host = 'https://fd8e6kvqc6bzfp19qou1.us-east-1.aoss.amazonaws.com'
index = 'coffee-products'
url = f'{host}/{index}/_search'

query = {
    'size': 100,
    'query': {'match_all': {}}
}

response = requests.get(url, auth=awsauth, json=query, headers={'Content-Type': 'application/json'})

if response.status_code != 200:
    print(f'Error: {response.status_code}')
    print(response.text)
    exit(1)

data = response.json()

print(f'Total products: {data["hits"]["total"]["value"]}')
print()

unsplash_count = 0
cloudfront_count = 0
other_count = 0

for hit in data['hits']['hits']:
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

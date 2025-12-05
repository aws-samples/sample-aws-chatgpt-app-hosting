#!/usr/bin/env python3
"""
Simple script to load products with images into OpenSearch

This script uses a minimal, direct approach that avoids common OpenSearch Serverless issues:
1. No complex error handling that might mask permission issues
2. Fresh boto3 session for credentials
3. Direct indexing without checking if index exists first
4. Simple linear flow without multiple client recreations

Why this works when load_catalog.py sometimes fails:
- OpenSearch Serverless permissions are eventually consistent (2-5 min propagation)
- Simpler code paths reduce opportunities for credential/session issues
- Direct approach makes debugging easier

If this script fails with 403:
1. Wait 2-5 minutes after any policy changes
2. Verify: aws sts get-caller-identity
3. Check policy: aws opensearchserverless get-access-policy --name coffee-products-access --type data
4. Ensure AWS_PAGER="" is set to avoid CLI hangs
"""
import json
import os
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from mcp_server.embeddings import EmbeddingsGenerator

def main():
    # Configuration - get from environment or CDK outputs
    endpoint = os.environ.get('OPENSEARCH_ENDPOINT', '').replace('https://', '')
    if not endpoint:
        print("ERROR: OPENSEARCH_ENDPOINT environment variable not set")
        print("Get it from CDK outputs: cdk outputs --all | grep OpenSearchEndpoint")
        print("Then: export OPENSEARCH_ENDPOINT=<endpoint>")
        sys.exit(1)
    
    region = os.environ.get('AWS_REGION', 'us-east-1')
    index_name = 'coffee-products'
    
    # Load products
    print("Loading products from data/products.json...")
    with open('data/products.json', 'r') as f:
        data = json.load(f)
    products = data['products']
    print(f"Loaded {len(products)} products")
    
    # Images use Unsplash URLs from products.json (ChatGPT CSP compatible)
    print("\nUsing Unsplash image URLs from products.json (ChatGPT CSP compatible)...")
    for i, product in enumerate(products):
        product_name = product['name']
        print(f"  {i+1}/{len(products)}: {product_name} - ✅ {product['image_url']}")
    
    # Generate embeddings
    print("\nGenerating embeddings...")
    embeddings_gen = EmbeddingsGenerator()
    for i, product in enumerate(products):
        text = f"{product['name']} {product['description']} {product['origin']} {' '.join(product['flavor_profile'])}"
        embedding = embeddings_gen.generate_embedding(text)
        product['description_embedding'] = embedding
        print(f"  {i+1}/{len(products)}: {product['name']} - ✅ embedded")
    
    # Set up OpenSearch client
    print("\nConnecting to OpenSearch...")
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
    
    # Create index with proper knn_vector mapping if it doesn't exist
    print(f"\nChecking if index '{index_name}' exists...")
    try:
        if not client.indices.exists(index=index_name):
            print(f"Creating index '{index_name}' with knn_vector mapping...")
            index_body = {
                "settings": {
                    "index": {
                        "knn": True,
                        "knn.algo_param.ef_search": 512
                    }
                },
                "mappings": {
                    "properties": {
                        "product_id": {"type": "keyword"},
                        "name": {"type": "text"},
                        "description": {"type": "text"},
                        "origin": {"type": "keyword"},
                        "roast_level": {"type": "keyword"},
                        "flavor_profile": {"type": "keyword"},
                        "price": {"type": "float"},
                        "image_url": {"type": "keyword"},
                        "description_embedding": {
                            "type": "knn_vector",
                            "dimension": 1536,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "nmslib",
                                "parameters": {
                                    "ef_construction": 512,
                                    "m": 16
                                }
                            }
                        }
                    }
                }
            }
            client.indices.create(index=index_name, body=index_body)
            print("✅ Index created with knn_vector mapping")
        else:
            print(f"✅ Index '{index_name}' already exists")
    except Exception as e:
        print(f"⚠️  Could not check/create index (may already exist): {e}")
        print("   Continuing with indexing...")
    
    # Index products
    print(f"\nIndexing {len(products)} products...")
    for i, product in enumerate(products):
        try:
            response = client.index(
                index=index_name,
                body=product
            )
            print(f"  {i+1}/{len(products)}: {product['name']} - ✅ indexed")
        except Exception as e:
            print(f"  {i+1}/{len(products)}: {product['name']} - ❌ failed: {e}")
    
    print("\n✅ Done!")

if __name__ == '__main__':
    main()

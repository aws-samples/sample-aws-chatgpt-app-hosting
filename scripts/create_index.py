#!/usr/bin/env python3
"""
Create OpenSearch index with proper knn_vector mapping
"""
import os
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import sys

def main():
    # Configuration
    endpoint = os.environ.get('OPENSEARCH_ENDPOINT', '').replace('https://', '')
    if not endpoint:
        print("ERROR: OPENSEARCH_ENDPOINT environment variable not set")
        sys.exit(1)
    
    region = os.environ.get('AWS_REGION', 'us-east-1')
    index_name = 'coffee-products'
    
    # Set up OpenSearch client
    print(f"Connecting to OpenSearch at {endpoint}...")
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
    
    # Delete existing index if it exists
    try:
        if client.indices.exists(index=index_name):
            print(f"Deleting existing index '{index_name}'...")
            client.indices.delete(index=index_name)
            print("✅ Deleted")
    except Exception as e:
        print(f"Note: Could not check/delete existing index: {e}")
    
    # Create index with proper mapping
    print(f"\nCreating index '{index_name}' with knn_vector mapping...")
    index_body = {
        "settings": {
            "index": {
                "knn": True,
                "knn.algo_param.ef_search": 512
            }
        },
        "mappings": {
            "properties": {
                "product_id": {
                    "type": "keyword"
                },
                "name": {
                    "type": "text"
                },
                "description": {
                    "type": "text"
                },
                "origin": {
                    "type": "keyword"
                },
                "roast_level": {
                    "type": "keyword"
                },
                "flavor_profile": {
                    "type": "keyword"
                },
                "price": {
                    "type": "float"
                },
                "image_url": {
                    "type": "keyword"
                },
                "image_base64": {
                    "type": "keyword",
                    "index": False,
                    "doc_values": False
                },
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
    
    try:
        response = client.indices.create(index=index_name, body=index_body)
        print(f"✅ Index '{index_name}' created successfully with knn_vector mapping")
    except Exception as e:
        print(f"❌ Failed to create index: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

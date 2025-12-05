#!/usr/bin/env python3
"""
Verify OpenSearch index mapping and sample data
"""
import os
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import sys
import json

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
    print("✅ Connected\n")
    
    # Get index mapping
    print(f"Index mapping for '{index_name}':")
    print("=" * 60)
    try:
        mapping = client.indices.get_mapping(index=index_name)
        properties = mapping[index_name]['mappings']['properties']
        
        for field, config in properties.items():
            field_type = config.get('type', 'N/A')
            if field_type == 'knn_vector':
                dimension = config.get('dimension', 'N/A')
                print(f"  {field}: {field_type} (dimension: {dimension})")
            else:
                print(f"  {field}: {field_type}")
    except Exception as e:
        print(f"❌ Error getting mapping: {e}")
        sys.exit(1)
    
    # Get document count
    print(f"\n{'=' * 60}")
    try:
        count = client.count(index=index_name)
        doc_count = count['count']
        print(f"Total documents: {doc_count}")
    except Exception as e:
        print(f"❌ Error counting documents: {e}")
        sys.exit(1)
    
    # Get sample document
    print(f"\n{'=' * 60}")
    print("Sample document:")
    try:
        result = client.search(
            index=index_name,
            body={"query": {"match_all": {}}, "size": 1}
        )
        if result['hits']['hits']:
            doc = result['hits']['hits'][0]['_source']
            print(f"  Product: {doc.get('name')}")
            print(f"  Origin: {doc.get('origin')}")
            print(f"  Roast: {doc.get('roast_level')}")
            print(f"  Price: ${doc.get('price')}")
            print(f"  Has embedding: {'description_embedding' in doc}")
            if 'description_embedding' in doc:
                print(f"  Embedding dimension: {len(doc['description_embedding'])}")
            print(f"  Has image: {'image_base64' in doc}")
    except Exception as e:
        print(f"❌ Error getting sample: {e}")
        sys.exit(1)
    
    print(f"\n{'=' * 60}")
    print("✅ Index verification complete!")

if __name__ == '__main__':
    main()

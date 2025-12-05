#!/bin/bash
# Quick check to see if products in OpenSearch have image_base64 field

echo "Checking OpenSearch for image_base64 fields..."
echo ""

# Get one product to inspect
OPENSEARCH_ENDPOINT="${OPENSEARCH_ENDPOINT:-https://fd8e6kvqc6bzfp19qou1.us-east-1.aoss.amazonaws.com}"
INDEX_NAME="coffee-products"

echo "Querying OpenSearch at: $OPENSEARCH_ENDPOINT"
echo "Index: $INDEX_NAME"
echo ""

# Use AWS CLI to query OpenSearch (requires awscurl or similar)
# For now, let's just check if the field exists in the index mapping

echo "Checking index mapping for image_base64 field..."
echo ""

# Try to get index mapping
aws opensearchserverless get-index \
  --collection-id fd8e6kvqc6bzfp19qou1 \
  --index-name $INDEX_NAME \
  2>/dev/null || echo "Note: AWS CLI opensearchserverless commands may not be available"

echo ""
echo "To manually verify:"
echo "1. Check the load_catalog.py logs to see if images were generated"
echo "2. Look for log messages like 'Successfully generated image for...'"
echo "3. Check the deployment-outputs.txt which says '24 products with AI-generated images'"

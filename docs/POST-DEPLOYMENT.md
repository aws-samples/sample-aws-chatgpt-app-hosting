# Post-Deployment Steps

After successfully deploying the CDK stacks, follow these steps to complete the setup.

## Prerequisites

- CDK deployment completed successfully
- CDK outputs saved (see below)
- Virtual environment activated: `source infrastructure/.venv/bin/activate`
- AWS credentials configured

## Required CDK Outputs

Save these values from your CDK deployment:

```bash
# From ImageHostingStack
export CLOUDFRONT_DOMAIN=<ProductImagesCDNDomain>
export S3_BUCKET=<ProductImagesBucketName>

# From ChatGPTAppAWSStack
export OPENSEARCH_ENDPOINT=<OpenSearchEndpoint>
export USER_POOL_ID=<CognitoUserPoolId>
export CLIENT_ID=<CognitoClientId>
```

Example values:
```bash
export CLOUDFRONT_DOMAIN=d14yhmh9aqdj57.cloudfront.net
export S3_BUCKET=imagehostingstack-productimagesbucket03bda4c8-y7ffydl9g4s9
export OPENSEARCH_ENDPOINT=https://cwwhdzyy20ysoy53ssij.us-east-1.aoss.amazonaws.com
export USER_POOL_ID=us-east-1_WqFXl0ME9
export CLIENT_ID=<your-cognito-client-id>
```

## Step 1: Generate and Upload Product Images

Generate AI images using Amazon Bedrock Nova Canvas and upload to S3:

```bash
# Activate virtual environment
source infrastructure/.venv/bin/activate

# Generate images (takes ~2 minutes for 24 products)
python3 scripts/generate_all_images.py
```

**What this does:**
- Generates 24 AI product images using Nova Canvas
- Uploads images to S3 bucket
- Updates `data/products.json` with CloudFront URLs
- Each image takes ~3-5 seconds to generate

**Expected output:**
```
Generating AI Images for All Products
======================================================================
[1/24] Processing: Ethiopian Yirgacheffe
  Product ID: ethiopian-yirgacheffe-light
  Generating image with Nova Canvas...
  ✓ Image generated (181786 bytes)
  Uploading to S3...
  ✓ Uploaded: https://d14yhmh9aqdj57.cloudfront.net/images/ethiopian-yirgacheffe-light.png
  Waiting 2s before next generation...
...
======================================================================
Summary:
  Total processed: 24
  Successful: 24
  Failed: 0
======================================================================
```

**Troubleshooting:**
- If generation fails, check Bedrock permissions
- Images are skipped if CloudFront URL already exists in products.json
- To regenerate all images, manually remove CloudFront URLs from products.json first

## Step 2: Create OpenSearch Index

Create the index with proper knn_vector mapping for semantic search:

```bash
python3 scripts/create_index.py
```

**What this does:**
- Deletes existing `coffee-products` index (if exists)
- Creates new index with knn_vector field (dimension: 1536)
- Configures HNSW algorithm for vector search

**Expected output:**
```
Connecting to OpenSearch at cwwhdzyy20ysoy53ssij.us-east-1.aoss.amazonaws.com...
✅ Connected
Deleting existing index 'coffee-products'...
✅ Deleted

Creating index 'coffee-products' with knn_vector mapping...
✅ Index 'coffee-products' created successfully with knn_vector mapping
```

**Important:** This step must be done before loading products. The knn_vector mapping cannot be added to an existing index.

## Step 3: Load Products into OpenSearch

Load all products with embeddings and CloudFront URLs:

```bash
python3 scripts/simple_load.py
```

**What this does:**
- Reads products from `data/products.json` (with CloudFront URLs)
- Generates vector embeddings using Bedrock Titan
- Indexes all 24 products into OpenSearch

**Expected output:**
```
Loading products from data/products.json...
Loaded 24 products

Using Unsplash image URLs from products.json (ChatGPT CSP compatible)...
  1/24: Ethiopian Yirgacheffe - ✅ https://d14yhmh9aqdj57.cloudfront.net/images/ethiopian-yirgacheffe-light.png
  ...

Generating embeddings...
  1/24: Ethiopian Yirgacheffe - ✅ embedded
  ...

Connecting to OpenSearch...
✅ Connected

Checking if index 'coffee-products' exists...
✅ Index 'coffee-products' already exists

Indexing 24 products...
  1/24: Ethiopian Yirgacheffe - ✅ indexed
  ...

✅ Done!
```

**Troubleshooting:**
- If you get 403 errors, wait 2-5 minutes for OpenSearch permissions to propagate
- If you get knn_vector errors, ensure Step 2 was completed successfully
- Script is idempotent - safe to run multiple times

## Step 4: Verify Setup

Verify that everything is working:

```bash
# Check CloudFront URLs in OpenSearch
python3 scripts/check_cloudfront_urls.py
```

**Expected output:**
```
Sample products from OpenSearch:
======================================================================
✓ CloudFront: Ethiopian Yirgacheffe
  URL: https://d14yhmh9aqdj57.cloudfront.net/images/ethiopian-yirgacheffe-light.png

✓ CloudFront: Colombian Supremo
  URL: https://d14yhmh9aqdj57.cloudfront.net/images/colombian-supremo-medium.png
...
======================================================================
CloudFront URLs found: 5/5
```

## Step 5: Create Test User (Optional)

If you want to test authentication:

```bash
# Create test user
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username testuser \
  --temporary-password TempPass123! \
  --message-action SUPPRESS

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username testuser \
  --password TestPass123! \
  --permanent
```

## Complete Setup Script

Run all steps in sequence:

```bash
#!/bin/bash
set -e

# Set environment variables from CDK outputs
export CLOUDFRONT_DOMAIN=<your-cloudfront-domain>
export S3_BUCKET=<your-s3-bucket>
export OPENSEARCH_ENDPOINT=<your-opensearch-endpoint>

# Activate virtual environment
source infrastructure/.venv/bin/activate

# Step 1: Generate and upload images
echo "Step 1: Generating AI images..."
python3 scripts/generate_all_images.py

# Step 2: Create OpenSearch index
echo "Step 2: Creating OpenSearch index..."
python3 scripts/create_index.py

# Step 3: Load products
echo "Step 3: Loading products into OpenSearch..."
python3 scripts/simple_load.py

# Step 4: Verify
echo "Step 4: Verifying setup..."
python3 scripts/check_cloudfront_urls.py

echo "✅ Post-deployment setup complete!"
```

## Summary

After completing these steps, you should have:

✅ 24 AI-generated product images in S3  
✅ CloudFront distribution serving images  
✅ OpenSearch index with knn_vector mapping  
✅ All products indexed with embeddings and CloudFront URLs  
✅ Lambda configured with CloudFront domain  

Your MCP server is now ready to use in ChatGPT!

## Next Steps

1. Configure the MCP server in ChatGPT using the MCPServerURL from CDK outputs
2. Test the coffee discovery experience
3. See `README.md` for usage examples

## Troubleshooting

### 403 Forbidden Errors
OpenSearch Serverless permissions are eventually consistent. Wait 2-5 minutes after deployment and retry.

### knn_vector Type Errors
The index was created without proper mapping. Run `python3 scripts/create_index.py` to recreate the index with correct mapping.

### Image Generation Failures
- Check Bedrock permissions for Nova Canvas
- Verify AWS credentials have access to `amazon.nova-canvas-v1:0` model
- Check CloudWatch logs for detailed error messages

### Missing CloudFront URLs
- Verify `generate_all_images.py` completed successfully
- Check `data/products.json` for CloudFront URLs
- Ensure S3 bucket and CloudFront distribution were created

For more help, see:
- `OPENSEARCH-QUICKREF.md`
- `CONTRIBUTING.md`
- `.kiro/steering/opensearch-troubleshooting.md`

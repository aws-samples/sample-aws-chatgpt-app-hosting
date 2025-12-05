# Reverted to Unsplash Images

## Summary

Removed S3 and CloudFront infrastructure due to ChatGPT's Content Security Policy restrictions. ChatGPT only allows images from specific whitelisted domains, and CloudFront is not on that list.

## What Was Removed

### Infrastructure (CDK)
- ❌ S3 bucket for product images
- ❌ CloudFront distribution
- ❌ Origin Access Identity (OAI)
- ❌ S3 permissions in Lambda role

### Code
- ❌ S3 upload logic in `scripts/simple_load.py`
- ❌ S3 upload logic in `scripts/load_catalog.py`
- ❌ `generate_and_upload_images_for_products()` function
- ❌ Image generation CLI arguments
- ❌ CloudFront URL handling

### Documentation
- ❌ `S3_CLOUDFRONT_MIGRATION.md`
- ❌ `QUICKSTART_S3_CLOUDFRONT.md`
- ❌ `DEPLOYMENT_SUCCESS.md`
- ❌ `DEPLOYMENT_CHECKLIST.md`
- ❌ `scripts/deploy_with_images.sh`

## What We Learned

### ChatGPT CSP Policy

ChatGPT's `img-src` Content Security Policy allows images only from:
1. `'self'` - Same origin
2. `https://cdn.tailwindcss.com`
3. `https://cdn.jsdelivr.net` ⭐
4. `https://unpkg.com` ⭐
5. `https://*.oaiusercontent.com`
6. `https://threejs.org`
7. `https://*.oaistatic.com`
8. `https://images.unsplash.com` ⭐ (currently using)

### Why CloudFront Didn't Work

- CloudFront domains (`*.cloudfront.net`) are NOT on ChatGPT's whitelist
- Data URIs (`data:image/...`) are also blocked
- Custom CloudFront domains would also be blocked unless whitelisted by OpenAI

## Current Solution

Using **Unsplash URLs** from `data/products.json`:
- ✅ CSP compliant (whitelisted by ChatGPT)
- ✅ Fast CDN delivery
- ✅ No infrastructure costs
- ✅ Images display correctly in ChatGPT
- ❌ Not AI-generated (stock photos)

## Future Options

If you want AI-generated images in ChatGPT, you could:

### Option 1: Use jsDelivr (Recommended)
- Host images in a GitHub repository
- Serve via `https://cdn.jsdelivr.net/gh/username/repo@branch/path/image.webp`
- jsDelivr is whitelisted by ChatGPT
- Free CDN with global edge locations

### Option 2: Use unpkg
- Publish images as an npm package
- Serve via `https://unpkg.com/package-name@version/path/image.webp`
- unpkg is whitelisted by ChatGPT
- Requires npm package management

### Option 3: Contact OpenAI
- Request CloudFront domain whitelisting (unlikely to succeed)
- Or request custom domain whitelisting

## Current State

### Infrastructure
- Cognito User Pool ✅
- OpenSearch Serverless ✅
- Lambda Function ✅
- API Gateway ✅
- S3 Bucket ❌ (removed)
- CloudFront ❌ (removed)

### Data
- 24 products in OpenSearch ✅
- Using Unsplash image URLs ✅
- Vector embeddings ✅
- No base64 images ✅

### Testing
- Images display in ChatGPT ✅
- No CSP errors ✅
- Fast response times ✅

## Files Modified

1. `infrastructure/stacks/coffee_discovery_stack.py` - Removed S3/CloudFront
2. `scripts/simple_load.py` - Removed S3 upload, use Unsplash URLs
3. `scripts/load_catalog.py` - Removed image generation function
4. Deleted documentation files

## Deployment

Infrastructure has been deployed without S3/CloudFront:
```bash
cd infrastructure
npx cdk deploy --require-approval never
```

Data has been reloaded with Unsplash URLs:
```bash
python3 scripts/simple_load.py
```

## Cost Impact

- **Before**: S3 + CloudFront = ~$1-2/month
- **After**: $0/month (using free Unsplash CDN)

## Next Steps

If you want to pursue AI-generated images:
1. Generate images locally using `scripts/image_generator.py`
2. Commit images to a GitHub repo
3. Update `data/products.json` with jsDelivr URLs
4. Reload data into OpenSearch

Otherwise, the current Unsplash solution works perfectly for ChatGPT.

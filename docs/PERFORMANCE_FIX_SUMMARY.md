# Performance Fix Summary - Base64 Image Issue

## Date: December 5, 2024

## Problem

After deploying the Nova Canvas image fix, ChatGPT searches were stalling/timing out with 500 errors.

## Root Cause

The base64-encoded PNG images are **too large** (~500KB each):
- Searching for 10 products = ~5MB of base64 data in the response
- Lambda timeout was only 30 seconds with 512MB memory
- The large payload was causing:
  - Slow Lambda execution
  - API Gateway timeouts
  - ChatGPT UI freezing
  - 500 Internal Server Error

## Solution Applied

### 1. Disabled Base64 Images in Response (For Now)

Modified `format_product_for_response()` to NOT include `image_base64` by default:

```python
def format_product_for_response(product: Dict, include_images: bool = False) -> Dict:
    # ...
    # Only include image_base64 if explicitly requested
    if include_images and "image_base64" in product and product["image_base64"]:
        formatted["image_base64"] = product["image_base64"]
    
    return formatted
```

**Result**: Responses now use `image_url` (Unsplash) again, which is fast and reliable.

### 2. Increased Lambda Resources

Updated Lambda configuration for better performance:
- **Timeout**: 30s → 60s
- **Memory**: 512MB → 1024MB

This provides headroom for future optimizations.

## Current Status

✅ **ChatGPT searches work normally** - Using Unsplash images  
✅ **Fast response times** - No more timeouts  
✅ **Nova Canvas images still in OpenSearch** - Available for future use  

## Why Base64 Images Don't Work

**The Problem with Base64 in JSON:**
1. Each image is ~378KB PNG → ~504KB base64
2. 10 products = ~5MB of text data
3. JSON parsing + network transfer + Lambda processing = slow
4. ChatGPT UI can't handle such large responses efficiently

**Better Alternatives (Future):**

### Option 1: Image CDN/S3 (Recommended)
- Store Nova Canvas images in S3
- Generate signed URLs or use CloudFront
- Update `image_url` to point to S3/CloudFront
- **Pros**: Fast, scalable, cacheable
- **Cons**: Requires S3 bucket + CloudFront setup

### Option 2: Separate Image Endpoint
- Create dedicated Lambda endpoint for images
- Return one image at a time by product_id
- **Pros**: Smaller responses
- **Cons**: Multiple API calls needed

### Option 3: Smaller Images
- Resize Nova Canvas images to 256x256 or 128x128
- Reduces base64 size by 75-90%
- **Pros**: Simple, works with current architecture
- **Cons**: Lower quality images

### Option 4: Image Compression
- Convert PNG to WebP or JPEG
- Compress before base64 encoding
- **Pros**: Smaller payloads
- **Cons**: Still large for JSON responses

## Recommendation

**For production use**, implement **Option 1 (S3 + CloudFront)**:

1. Create S3 bucket for product images
2. Upload Nova Canvas images to S3 during catalog loading
3. Set up CloudFront distribution
4. Update `image_url` field to point to CloudFront URLs
5. Remove `image_base64` from OpenSearch (save storage)

This provides:
- Fast image loading
- CDN caching
- No Lambda payload issues
- Professional image delivery

## Files Modified

- `mcp_server/tools.py` - Added `include_images` parameter (default False)
- `lambda/mcp_server/tools.py` - Same change
- `infrastructure/stacks/coffee_discovery_stack.py` - Increased timeout and memory

## Testing

The application now works normally with Unsplash images. To test:

```bash
# In ChatGPT, search for:
"I want a fruity light roast coffee"

# Should return results quickly with Unsplash images
```

## Conclusion

Base64 images in JSON responses are not viable for this use case. The Nova Canvas images are valuable and should be served via S3/CloudFront for optimal performance.

For now, the application uses Unsplash images which provide good visual representation and fast loading times.

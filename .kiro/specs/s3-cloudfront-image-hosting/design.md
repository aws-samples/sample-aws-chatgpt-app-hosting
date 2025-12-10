# Design Document

## Overview

This feature adds AWS infrastructure for hosting product images using S3 and CloudFront CDN. Images will be stored in a private S3 bucket (chatgpt-apps-aws) and served through CloudFront with Origin Access Identity (OAI) for security. The design includes proper CORS and CSP configuration to ensure images load correctly in the ChatGPT iframe without cross-origin or security policy violations. Implementation starts with a single test image to validate the complete pipeline before migrating all products.

## Architecture

### High-Level Flow

1. **Infrastructure Setup**:
   - CDK creates S3 bucket with private access
   - CDK creates CloudFront distribution with OAI
   - CDK configures CORS on S3 bucket
   - CDK adds CSP headers to CloudFront responses

2. **Image Upload Flow**:
   - Upload script reads image file or downloads from URL
   - Script uploads image to S3 with proper metadata
   - Script generates CloudFront URL
   - Script updates products.json with CloudFront URL

3. **Image Delivery Flow**:
   - Web component requests image from CloudFront URL
   - CloudFront checks cache (edge location)
   - If cache miss, CloudFront fetches from S3 via OAI
   - CloudFront serves image with CORS and CSP headers
   - Browser renders image in web component

### Component Interactions

```
┌─────────────────┐
│  CDK Stack      │
│  - S3 Bucket    │
│  - CloudFront   │
│  - OAI          │
│  - CORS Config  │
└────────┬────────┘
         │
         ↓
┌─────────────────┐      ┌──────────────────┐
│ Upload Script   │─────→│  S3 Bucket       │
│ - Read image    │      │  (Private)       │
│ - Upload to S3  │      └────────┬─────────┘
│ - Generate URL  │               │
└─────────────────┘               │ OAI Only
                                  ↓
                         ┌──────────────────┐
                         │  CloudFront CDN  │
                         │  - CORS Headers  │
                         │  - CSP Headers   │
                         │  - Caching       │
                         └────────┬─────────┘
                                  │
                                  ↓
                         ┌──────────────────┐
                         │  Web Component   │
                         │  (ChatGPT)       │
                         └──────────────────┘
```

## Components and Interfaces

### 1. S3 Bucket Configuration

**CDK Resource**: `aws_s3.Bucket`

**Configuration**:
```python
bucket = s3.Bucket(
    self,
    "ProductImagesBucket",
    bucket_name="chatgpt-apps-aws",
    block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
    encryption=s3.BucketEncryption.S3_MANAGED,
    cors=[
        s3.CorsRule(
            allowed_methods=[s3.HttpMethods.GET, s3.HttpMethods.HEAD],
            allowed_origins=["*"],
            allowed_headers=["*"],
            exposed_headers=["ETag"],
            max_age=Duration.hours(1)
        )
    ],
    removal_policy=RemovalPolicy.RETAIN,  # Prevent accidental deletion
)
```

**CORS Configuration**:
- **Allowed Methods**: GET, HEAD (read-only access)
- **Allowed Origins**: * (any origin can request images)
- **Allowed Headers**: * (accept any request headers)
- **Exposed Headers**: ETag (for caching validation)
- **Max Age**: 1 hour (cache preflight requests)

**Security**:
- Block all public access
- S3-managed encryption at rest
- Access only via CloudFront OAI

### 2. CloudFront Distribution

**CDK Resource**: `aws_cloudfront.Distribution`

**Note on OAI vs OAC**:
- **OAI (Origin Access Identity)**: Legacy method, easier to configure in CDK
- **OAC (Origin Access Control)**: Newer method, more secure, uses SigV4
- For this implementation, we'll use **OAI** for simplicity (CDK has better support)
- OAC can be added later if needed (requires manual bucket policy configuration)

**Configuration**:
```python
# Create Origin Access Identity
oai = cloudfront.OriginAccessIdentity(
    self,
    "ProductImagesOAI",
    comment="OAI for chatgpt-apps-aws bucket"
)

# Grant OAI read access to bucket
bucket.grant_read(oai)

# Create CloudFront distribution
distribution = cloudfront.Distribution(
    self,
    "ProductImagesCDN",
    default_behavior=cloudfront.BehaviorOptions(
        origin=origins.S3Origin(
            bucket,
            origin_access_identity=oai
        ),
        viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
        cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD,
        compress=True,
        cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
        response_headers_policy=create_response_headers_policy(self)
    ),
    price_class=cloudfront.PriceClass.PRICE_CLASS_100,  # Use all edge locations
    http_version=cloudfront.HttpVersion.HTTP2_AND_3,
    enable_ipv6=True,
)
```

**Response Headers Policy**:
```python
def create_response_headers_policy(scope):
    return cloudfront.ResponseHeadersPolicy(
        scope,
        "ProductImagesResponseHeaders",
        cors_behavior=cloudfront.ResponseHeadersCorsBehavior(
            access_control_allow_origins=cloudfront.ResponseHeadersAccessControlAllowOrigins.all(),
            access_control_allow_methods=["GET", "HEAD"],
            access_control_allow_headers=["*"],
            access_control_expose_headers=["ETag"],
            access_control_max_age=Duration.hours(24),
            origin_override=True
        ),
        security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
            strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(
                access_control_max_age=Duration.days(365),
                include_subdomains=True,
                override=True
            )
        ),
        custom_headers_behavior=cloudfront.ResponseCustomHeadersBehavior(
            custom_headers=[
                cloudfront.ResponseCustomHeader(
                    header="Cache-Control",
                    value="public, max-age=86400, immutable",
                    override=True
                )
            ]
        )
    )
```

**Note**: CSP headers are NOT configured in CloudFront because ChatGPT controls CSP via the MCP server's `openai/widgetCSP` metadata.

**Key Features**:
- **HTTPS Only**: Redirect HTTP to HTTPS
- **Compression**: Enable gzip/brotli compression
- **HTTP/2 and HTTP/3**: Modern protocols for faster loading
- **Global Distribution**: All edge locations (PriceClass 100)
- **Optimized Caching**: 24-hour cache with immutable flag

### 3. Image Upload Script

**Location**: `scripts/upload_image.py` (new file)

**Interface**:
```python
def upload_image_to_s3(
    image_source: str,
    product_id: str,
    bucket_name: str = "chatgpt-apps-aws",
    cloudfront_domain: str = None
) -> str:
    """Upload image to S3 and return CloudFront URL.
    
    Args:
        image_source: Local file path or HTTP URL
        product_id: Product identifier for S3 key
        bucket_name: S3 bucket name
        cloudfront_domain: CloudFront distribution domain
        
    Returns:
        CloudFront URL for the uploaded image
        
    Raises:
        ValueError: If image source is invalid
        boto3.exceptions.S3UploadFailedError: If upload fails
    """
```

**Implementation Details**:
```python
import boto3
import requests
from pathlib import Path
from typing import Optional
import mimetypes

def upload_image_to_s3(image_source, product_id, bucket_name, cloudfront_domain):
    s3_client = boto3.client('s3')
    
    # Determine if source is URL or file path
    if image_source.startswith('http://') or image_source.startswith('https://'):
        # Download from URL
        response = requests.get(image_source, timeout=30)
        response.raise_for_status()
        image_data = response.content
        
        # Detect content type from response headers
        content_type = response.headers.get('Content-Type', 'image/jpeg')
    else:
        # Read from local file
        image_path = Path(image_source)
        if not image_path.exists():
            raise ValueError(f"Image file not found: {image_source}")
        
        image_data = image_path.read_bytes()
        
        # Detect content type from file extension
        content_type, _ = mimetypes.guess_type(str(image_path))
        if not content_type:
            content_type = 'image/jpeg'
    
    # Determine file extension from content type
    ext_map = {
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/webp': 'webp',
        'image/gif': 'gif'
    }
    ext = ext_map.get(content_type, 'jpg')
    
    # Generate S3 key
    s3_key = f"images/{product_id}.{ext}"
    
    # Upload to S3
    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=image_data,
        ContentType=content_type,
        CacheControl='public, max-age=86400, immutable',
        Metadata={
            'product_id': product_id,
            'uploaded_by': 'upload_script'
        }
    )
    
    # Generate CloudFront URL
    cloudfront_url = f"https://{cloudfront_domain}/{s3_key}"
    
    return cloudfront_url
```

### 4. Test Image Upload Script

**Location**: `scripts/test_single_image.py` (new file)

**Purpose**: Upload one test image and update products.json

**Implementation**:
```python
import json
from pathlib import Path
from upload_image import upload_image_to_s3

def test_single_image():
    # Configuration
    PRODUCTS_FILE = Path("data/products.json")
    TEST_PRODUCT_ID = "ethiopian-yirgacheffe-light"  # First product
    CLOUDFRONT_DOMAIN = "d1234567890abc.cloudfront.net"  # From CDK output
    
    # Load products
    with open(PRODUCTS_FILE) as f:
        data = json.load(f)
    
    # Find test product
    test_product = next(
        (p for p in data['products'] if p['product_id'] == TEST_PRODUCT_ID),
        None
    )
    
    if not test_product:
        raise ValueError(f"Product {TEST_PRODUCT_ID} not found")
    
    print(f"Testing with product: {test_product['name']}")
    print(f"Current image URL: {test_product['image_url']}")
    
    # Upload image (download from Unsplash URL)
    cloudfront_url = upload_image_to_s3(
        image_source=test_product['image_url'],
        product_id=TEST_PRODUCT_ID,
        bucket_name="chatgpt-apps-aws",
        cloudfront_domain=CLOUDFRONT_DOMAIN
    )
    
    print(f"Uploaded to CloudFront: {cloudfront_url}")
    
    # Update products.json
    test_product['image_url'] = cloudfront_url
    test_product['image_source'] = 'cloudfront'  # Track source
    
    with open(PRODUCTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Updated {PRODUCTS_FILE}")
    print("\nNext steps:")
    print("1. Run: python3 scripts/load_catalog.py")
    print("2. Test in ChatGPT to verify image loads")
    print("3. Check browser console for CORS/CSP errors")

if __name__ == "__main__":
    test_single_image()
```

### 5. Lambda IAM Permissions Update

**Location**: `infrastructure/stacks/coffee_discovery_stack.py` (modified)

**Changes**:
```python
# Add S3 read permissions to Lambda role
lambda_role.add_to_policy(
    iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        actions=[
            "s3:GetObject",
            "s3:ListBucket",
        ],
        resources=[
            f"arn:aws:s3:::chatgpt-apps-aws",
            f"arn:aws:s3:::chatgpt-apps-aws/*",
        ],
    )
)
```

### 6. MCP Tools CSP Configuration

**Location**: `mcp_server/tools.py` (modified)

**Critical Change**: Add CloudFront domain to `openai/widgetCSP` metadata

```python
def search_products(
    preferences: str,
    origin: Optional[str] = None,
    roast_level: Optional[str] = None,
    max_price: Optional[float] = None,
    flavor_profile: Optional[List[str]] = None,
    exclude_ids: Optional[List[str]] = None,
) -> types.TextContent:
    """Search for coffee products based on preferences."""
    
    # ... existing search logic ...
    
    # Return results with CSP configuration
    return types.TextContent(
        type="text",
        text=json.dumps({
            "products": results,
            "count": len(results)
        }),
        annotations={
            "openai/outputTemplate": "ui://widget/coffee-discovery.html",
            "openai/toolInvocation/invoking": "Searching for coffee...",
            "openai/toolInvocation/invoked": "Found coffee products",
            "openai/widgetAccessible": True,
            "openai/resultCanProduceWidget": True,
            "openai/widgetCSP": {
                "resource_domains": [
                    os.environ.get("CLOUDFRONT_DOMAIN", "https://d1234567890abc.cloudfront.net"),
                ]
            },
        }
    )
```

**Environment Variable**:
- Add `CLOUDFRONT_DOMAIN` to Lambda environment variables
- CDK will set this from CloudFront distribution output
- Format: `https://d1234567890abc.cloudfront.net` (no trailing slash)

### 7. Web Component Updates

**Location**: `mcp_server/web_component.html` (no changes needed)

**Current Implementation**: Already handles CloudFront URLs correctly

The web component already has proper error handling:
```javascript
<img 
    class="product-image" 
    src="${imageSrc}" 
    alt="${escapeHtml(product.name)}"
    onerror="this.src='data:image/svg+xml,...'"
/>
```

**No changes needed** - the component will automatically use CloudFront URLs from `image_url` field.

## Data Models

### Product Document (Updated)

```json
{
  "product_id": "ethiopian-yirgacheffe-light",
  "name": "Ethiopian Yirgacheffe",
  "description": "...",
  "origin": "Ethiopia",
  "roast_level": "light",
  "flavor_profile": ["floral", "fruity", "citrus"],
  "price": 18.99,
  "image_url": "https://d1234567890abc.cloudfront.net/images/ethiopian-yirgacheffe-light.jpg",
  "image_source": "cloudfront",
  "embedding": [...]
}
```

**New/Modified Fields**:
- `image_url`: Now points to CloudFront URL instead of Unsplash
- `image_source`: Optional field to track image source (cloudfront, unsplash, base64)

### S3 Object Structure

```
s3://chatgpt-apps-aws/
  └── images/
      ├── ethiopian-yirgacheffe-light.jpg
      ├── colombian-supremo-medium.jpg
      ├── brazilian-santos-dark.jpg
      └── ...
```

**S3 Object Metadata**:
- `Content-Type`: image/jpeg, image/png, or image/webp
- `Cache-Control`: public, max-age=86400, immutable
- `Metadata.product_id`: Product identifier
- `Metadata.uploaded_by`: Script or user identifier

## CORS and CSP Configuration

### CORS Headers (S3 Bucket)

```xml
<CORSConfiguration>
  <CORSRule>
    <AllowedOrigin>*</AllowedOrigin>
    <AllowedMethod>GET</AllowedMethod>
    <AllowedMethod>HEAD</AllowedMethod>
    <AllowedHeader>*</AllowedHeader>
    <ExposeHeader>ETag</ExposeHeader>
    <MaxAgeSeconds>3600</MaxAgeSeconds>
  </CORSRule>
</CORSConfiguration>
```

**Why These Settings**:
- `AllowedOrigin: *`: ChatGPT iframe origin varies, allow all
- `AllowedMethod: GET, HEAD`: Read-only access for images
- `AllowedHeader: *`: Accept any request headers
- `ExposeHeader: ETag`: Enable cache validation
- `MaxAgeSeconds: 3600`: Cache preflight for 1 hour

### CORS Headers (CloudFront Response)

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, HEAD
Access-Control-Allow-Headers: *
Access-Control-Expose-Headers: ETag
Access-Control-Max-Age: 86400
```

**Why CloudFront CORS**:
- CloudFront adds CORS headers to all responses
- Ensures CORS works even if S3 CORS fails
- `origin_override: True` means CloudFront headers take precedence

### CSP Headers (MCP Server Configuration)

**IMPORTANT**: ChatGPT controls CSP via the MCP server's tool metadata, NOT via CloudFront headers.

**Configuration in MCP Server** (`mcp_server/tools.py`):
```python
def _tool_meta(tool_name: str) -> Dict[str, Any]:
    return {
        "openai/outputTemplate": f"ui://widget/{tool_name}.html",
        "openai/toolInvocation/invoking": "Loading products...",
        "openai/toolInvocation/invoked": "Products loaded",
        "openai/widgetAccessible": True,
        "openai/resultCanProduceWidget": True,
        "openai/widgetCSP": {
            "resource_domains": [
                "https://d1234567890abc.cloudfront.net",  # Your CloudFront domain
            ]
        },
    }
```

**CSP Configuration Explained**:
- `resource_domains`: List of domains allowed for loading resources (images, scripts, styles)
- ChatGPT automatically generates CSP headers: `script-src`, `style-src`, `img-src`, `font-src`
- Only domains in `resource_domains` can load resources
- `data:` URIs are automatically allowed for fallback

**Why This Approach**:
- ChatGPT's iframe has strict CSP that blocks external resources
- `openai/widgetCSP` tells ChatGPT which domains to allow
- CloudFront CSP headers are ignored (ChatGPT controls CSP)
- Must include CloudFront domain in `resource_domains` for images to load

**Common CSP Issues**:
- **Blocked Image**: CloudFront domain not in `resource_domains`
- **Blocked API**: `connect-src` cannot be configured (ChatGPT limitation)
- **Blocked Font**: Add font CDN to `resource_domains` if using web fonts

### Testing CORS and CSP

**Test CORS with curl**:
```bash
curl -I \
  -H "Origin: https://chatgpt.com" \
  -H "Access-Control-Request-Method: GET" \
  https://d1234567890abc.cloudfront.net/images/test.jpg
```

**Expected Response**:
```
HTTP/2 200
access-control-allow-origin: *
access-control-allow-methods: GET, HEAD
access-control-expose-headers: ETag
cache-control: public, max-age=86400, immutable
content-type: image/jpeg
```

**Test CSP in Browser**:
1. Open ChatGPT with web component
2. Open browser DevTools (F12)
3. Check Console for CSP violations
4. Check Network tab for CORS errors

**Common Issues**:
- **CORS Error**: "No 'Access-Control-Allow-Origin' header"
  - Solution: Verify CloudFront response headers policy
- **CSP Violation**: "Refused to load image"
  - Solution: Add CloudFront domain to img-src directive
- **Mixed Content**: "Blocked loading mixed active content"
  - Solution: Ensure all URLs use HTTPS

## Error Handling

### Upload Failures

**Network Errors**:
- Retry up to 3 times with exponential backoff
- Log error details for debugging
- Continue with next image if upload fails

**Invalid Image Format**:
- Validate image format before upload
- Support JPEG, PNG, WebP, GIF
- Reject unsupported formats with clear error message

**S3 Permissions**:
- Verify IAM credentials have s3:PutObject permission
- Check bucket policy allows uploads
- Provide clear error message if permission denied

### Image Loading Failures

**404 Not Found**:
- Display fallback SVG placeholder
- Log error to console for debugging
- Don't break web component rendering

**CORS Errors**:
- Check CloudFront response headers
- Verify CORS configuration on S3 and CloudFront
- Test with curl to isolate issue

**CSP Violations**:
- Check browser console for specific violation
- Update CSP headers in CloudFront response policy
- Test in ChatGPT iframe environment

## Testing Strategy

### Unit Tests

**Upload Script**:
- Test uploading from local file
- Test downloading and uploading from URL
- Test content type detection
- Test S3 key generation
- Test CloudFront URL generation

**CDK Stack**:
- Test S3 bucket creation with correct configuration
- Test CloudFront distribution with OAI
- Test CORS configuration
- Test response headers policy

### Integration Tests

**End-to-End Flow**:
1. Deploy CDK stack
2. Upload test image
3. Update products.json
4. Run load_catalog.py
5. Test in ChatGPT
6. Verify image loads without errors

**CORS Testing**:
1. Test preflight OPTIONS request
2. Test GET request with Origin header
3. Verify Access-Control-* headers in response
4. Test from ChatGPT iframe origin

**CSP Testing**:
1. Load web component in ChatGPT
2. Check browser console for CSP violations
3. Verify images load successfully
4. Test fallback SVG placeholder

### Manual Testing Checklist

- [ ] S3 bucket created with private access
- [ ] CloudFront distribution created with OAI
- [ ] Test image uploaded to S3
- [ ] CloudFront URL generated correctly
- [ ] products.json updated with CloudFront URL
- [ ] Image loads in web component
- [ ] No CORS errors in browser console
- [ ] No CSP violations in browser console
- [ ] Image loads fast (CDN caching working)
- [ ] Fallback placeholder works for missing images

## Performance Considerations

### CloudFront Caching

**Cache Behavior**:
- Cache images for 24 hours (86400 seconds)
- Use `immutable` flag to prevent revalidation
- Compress images with gzip/brotli

**Cache Key**:
- Include full S3 key in cache key
- Don't include query strings (not used)
- Don't include cookies (not needed)

**Cache Hit Ratio**:
- Expected: >95% after warm-up period
- Monitor via CloudFront metrics
- Invalidate cache when images change

### Image Optimization

**Format Selection**:
- Use WebP for modern browsers (smaller size)
- Fallback to JPEG for compatibility
- PNG for images requiring transparency

**Size Optimization**:
- Resize images to max 800x600 pixels
- Compress JPEG at 85% quality
- Use progressive JPEG for faster perceived loading

**Future Enhancements**:
- Implement responsive images (srcset)
- Generate multiple sizes (thumbnails, full-size)
- Use CloudFront image optimization (Lambda@Edge)

### Network Performance

**HTTP/2 and HTTP/3**:
- Enable multiplexing for parallel requests
- Reduce connection overhead
- Faster loading on high-latency networks

**Global Distribution**:
- Use all CloudFront edge locations
- Reduce latency for international users
- Typical latency: <50ms from edge location

## Security Considerations

### S3 Bucket Security

**Private Access**:
- Block all public access
- Access only via CloudFront OAI
- No bucket policies allowing public read

**Encryption**:
- S3-managed encryption at rest (SSE-S3)
- HTTPS in transit (enforced by CloudFront)
- No unencrypted access allowed

**Access Logging**:
- Enable S3 access logging (optional)
- Monitor for unauthorized access attempts
- Alert on suspicious patterns

### CloudFront Security

**HTTPS Only**:
- Redirect HTTP to HTTPS
- Use TLS 1.2 or higher
- Strong cipher suites only

**Origin Access Identity**:
- CloudFront uses OAI to access S3
- S3 bucket policy grants access only to OAI
- No direct S3 access possible

**DDoS Protection**:
- AWS Shield Standard (automatic)
- Rate limiting via AWS WAF (optional)
- CloudFront absorbs traffic spikes

### Content Security

**Image Validation**:
- Validate image format before upload
- Scan for malicious content (optional)
- Reject executable files

**Access Control**:
- IAM policies for upload permissions
- Separate read/write permissions
- Audit trail via CloudTrail

## Deployment Considerations

### CDK Deployment

**Order of Operations**:
1. Create S3 bucket
2. Create Origin Access Identity
3. Grant OAI access to bucket
4. Create CloudFront distribution
5. Output CloudFront domain name

**Deployment Time**:
- S3 bucket: ~30 seconds
- CloudFront distribution: ~15-20 minutes
- Total: ~20-25 minutes

**Rollback Plan**:
- CDK stack can be destroyed
- S3 bucket has RETAIN policy (manual deletion required)
- CloudFront distribution can be disabled

### Migration Strategy

**Phase 1: Infrastructure Setup**
- Deploy CDK stack
- Verify S3 and CloudFront created
- Test CORS and CSP configuration

**Phase 2: Single Image Test**
- Upload one test image
- Update one product in products.json
- Test in ChatGPT
- Verify no CORS/CSP errors

**Phase 3: Gradual Migration**
- Upload images for 5 products
- Test in ChatGPT
- Monitor for issues
- Continue if successful

**Phase 4: Full Migration**
- Upload all remaining images
- Update all products in products.json
- Run load_catalog.py
- Verify all images load correctly

**Phase 5: Cleanup**
- Remove Unsplash URLs from products.json
- Document CloudFront domain
- Update README with new architecture

### Backward Compatibility

**Fallback Mechanism**:
- Web component already has fallback SVG
- Products without CloudFront URLs still work
- Can mix CloudFront and Unsplash URLs during migration

**No Breaking Changes**:
- image_url field format unchanged (still a URL)
- Web component requires no code changes
- MCP tools require no changes

## Dependencies

### AWS Services

- **S3**: Object storage for images
- **CloudFront**: CDN for fast delivery
- **IAM**: Permissions for Lambda and OAI
- **CloudFormation**: CDK deployment

### Python Libraries

**New Dependencies** (add to `scripts/requirements.txt`):
```
boto3>=1.28.0  # Already present
requests>=2.31.0  # For downloading images from URLs
Pillow>=10.0.0  # For image validation and optimization (optional)
```

### Configuration

**Environment Variables**:
- `AWS_REGION`: AWS region (default: us-east-1)
- `CLOUDFRONT_DOMAIN`: CloudFront distribution domain (from CDK output)

**CDK Outputs**:
- `ProductImagesBucketName`: S3 bucket name
- `ProductImagesCDNDomain`: CloudFront distribution domain
- `ProductImagesCDNDistributionId`: CloudFront distribution ID (for invalidation)

## Monitoring and Observability

### CloudWatch Metrics

**S3 Metrics**:
- NumberOfObjects: Track image count
- BucketSizeBytes: Monitor storage usage
- AllRequests: Monitor S3 access (should be low with CloudFront)

**CloudFront Metrics**:
- Requests: Total requests to CDN
- BytesDownloaded: Data transfer volume
- CacheHitRate: Percentage of requests served from cache
- 4xxErrorRate: Client errors (404, 403)
- 5xxErrorRate: Server errors

### Logging

**S3 Access Logs** (optional):
- Log all S3 access attempts
- Useful for security auditing
- Store in separate logging bucket

**CloudFront Access Logs** (optional):
- Log all CloudFront requests
- Analyze traffic patterns
- Debug CORS/CSP issues

### Alerts

**Recommended Alarms**:
- CloudFront 5xx error rate > 1%
- CloudFront cache hit rate < 90%
- S3 bucket size > 10GB (cost control)
- Unusual traffic patterns (security)

## Cost Estimation

### S3 Storage

- **Storage**: $0.023 per GB/month (Standard)
- **Estimated**: 24 images × 100KB = 2.4MB = $0.00006/month
- **Negligible cost** for small catalog

### CloudFront

- **Data Transfer**: $0.085 per GB (first 10TB)
- **Requests**: $0.0075 per 10,000 requests
- **Estimated**: 1000 requests/day × 100KB = 3GB/month = $0.26/month
- **Very low cost** with caching

### Total Estimated Cost

- **Monthly**: ~$0.30/month
- **Annual**: ~$3.60/year
- **Significantly cheaper** than commercial CDN services

## Future Enhancements

1. **Automatic Image Optimization**:
   - Lambda@Edge for on-the-fly resizing
   - WebP conversion for modern browsers
   - Responsive images (srcset)

2. **Image Upload UI**:
   - Web interface for uploading images
   - Drag-and-drop support
   - Bulk upload capability

3. **AI Image Generation Integration**:
   - Generate images with Nova Canvas
   - Upload directly to S3
   - Skip base64 encoding in OpenSearch

4. **Advanced Caching**:
   - Vary cache by device type
   - Preload images for popular products
   - Predictive prefetching

5. **Analytics**:
   - Track image view counts
   - Identify popular products
   - Optimize cache based on usage

# Design Document

## Overview

This feature integrates Amazon Bedrock Nova Canvas to generate custom product images for the Coffee Discovery application. Images are generated during catalog loading, encoded as base64, and stored directly in OpenSearch documents. The web component is updated to render images using data URIs, eliminating the need for external image hosting infrastructure.

## Architecture

### High-Level Flow

1. **Catalog Loading Phase**:
   - Load script reads products from `data/products.json`
   - For each product, generate a descriptive prompt
   - Call Nova Canvas API to generate product image
   - Convert image bytes to base64 encoding
   - Store base64 string in OpenSearch document

2. **Search Phase** (unchanged):
   - MCP tools query OpenSearch for products
   - Product documents include image_base64 field
   - Results returned to web component

3. **Rendering Phase**:
   - Web component receives products with image_base64
   - Construct data URI: `data:image/png;base64,{base64_string}`
   - Render images in product tiles

### Component Interactions

```
load_catalog.py
    ↓
Nova Canvas API (Bedrock)
    ↓
Base64 Encoder
    ↓
OpenSearch (with image_base64 field)
    ↓
MCP Tools (search_products, etc.)
    ↓
Web Component (data URI rendering)
```

## Components and Interfaces

### 1. Image Generation Module

**Location**: `scripts/image_generator.py` (new file)

**Responsibilities**:
- Generate prompts from product data
- Call Bedrock Nova Canvas API
- Handle retries and error cases
- Validate generated images

**Interface**:
```python
def generate_product_image(
    product: dict,
    model_id: str = "amazon.nova-canvas-v1:0",
    width: int = 512,
    height: int = 512,
    max_retries: int = 3
) -> Optional[bytes]:
    """Generate product image using Nova Canvas.
    
    Args:
        product: Product dictionary with name, description, origin, roast_level
        model_id: Bedrock model ID for Nova Canvas
        width: Image width in pixels
        height: Image height in pixels
        max_retries: Maximum retry attempts
        
    Returns:
        Image bytes (PNG format) or None if generation fails
    """
```


**Prompt Generation**:
```python
def create_image_prompt(product: dict) -> str:
    """Create Nova Canvas prompt from product data.
    
    Template:
    "A professional product photograph of a premium coffee bag labeled 
    '{product_name}'. The bag is a {roast_level} roast coffee from {origin}. 
    {description}. The product name '{product_name}' is prominently displayed 
    on the label. Studio lighting, white background, commercial product 
    photography style, high quality, detailed."
    """
```

### 2. Base64 Encoding Module

**Location**: `scripts/image_generator.py`

**Responsibilities**:
- Convert image bytes to base64 string
- Validate encoding correctness

**Interface**:
```python
def encode_image_base64(image_bytes: bytes) -> str:
    """Encode image bytes as base64 string.
    
    Args:
        image_bytes: Raw image data (PNG format)
        
    Returns:
        Base64-encoded string without line breaks
    """
```

### 3. Updated Load Script

**Location**: `scripts/load_catalog.py` (modified)

**Changes**:
- Add command-line arguments for image generation control
- Integrate image generation before indexing
- Add progress tracking and logging
- Handle image generation failures gracefully

**New Command-Line Arguments**:
```python
--skip-images: Skip image generation entirely
--regenerate-images: Force regeneration of all images
--image-width: Image width in pixels (default: 512)
--image-height: Image height in pixels (default: 512)
```

### 4. OpenSearch Schema Update

**Index Mapping Addition**:
```json
{
  "mappings": {
    "properties": {
      "image_base64": {
        "type": "keyword",
        "index": false,
        "doc_values": false
      }
    }
  }
}
```

**Rationale**: 
- `keyword` type for exact storage
- `index: false` since we never search on image data
- `doc_values: false` to save disk space

### 5. Web Component Update

**Location**: `mcp_server/web_component.html` (modified)

**Changes**:
- Update image rendering logic to check for image_base64
- Construct data URIs when base64 is available
- Fall back to image_url when base64 is missing

**Image Source Logic**:
```javascript
function getImageSource(product) {
    if (product.image_base64) {
        return `data:image/png;base64,${product.image_base64}`;
    }
    return product.image_url || '';
}
```

## Data Models

### Product Document (Updated)

```json
{
  "product_id": "string",
  "name": "string",
  "description": "string",
  "origin": "string",
  "roast_level": "string",
  "flavor_profile": ["string"],
  "price": "float",
  "image_url": "string",
  "image_base64": "string",
  "embedding": [float]
}
```

**New Field**:
- `image_base64`: Base64-encoded PNG image (50-150KB encoded size)

**Backward Compatibility**:
- `image_url` retained as fallback
- Products without `image_base64` still render using `image_url`


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Prompt completeness

*For any* product with name, description, origin, and roast_level fields, the generated prompt should contain all four values as substrings.

**Validates: Requirements 1.2, 6.1, 6.2, 6.3**

### Property 2: Prompt styling keywords

*For any* generated prompt, it should contain the keywords "professional", "product photography", "studio lighting", and "white background".

**Validates: Requirements 1.3, 6.4, 6.5**

### Property 3: Image generation produces data

*For any* successful image generation call, the returned bytes should be non-empty and have size greater than 1KB.

**Validates: Requirements 1.4, 8.1**

### Property 4: Base64 encoding round-trip

*For any* image bytes, encoding to base64 and then decoding should produce the original bytes.

**Validates: Requirements 2.1, 8.3**

### Property 5: Base64 encoding format

*For any* base64-encoded string produced by the system, it should not contain newline characters (\\n or \\r).

**Validates: Requirements 2.5**

### Property 6: Document size bounds

*For any* product document with image_base64, the total document size should be less than 1MB (well under OpenSearch's 100MB limit).

**Validates: Requirements 2.4**

### Property 7: Image field presence

*For any* product successfully processed with image generation enabled, the indexed OpenSearch document should contain the image_base64 field.

**Validates: Requirements 2.2**

### Property 8: Data URI construction

*For any* product with image_base64 field, the constructed data URI should start with "data:image/png;base64," followed by the base64 string.

**Validates: Requirements 3.1, 3.5**

### Property 9: Image source priority

*For any* product with both image_base64 and image_url fields, the web component should use the data URI constructed from image_base64 as the image source.

**Validates: Requirements 3.3**

### Property 10: Fallback behavior

*For any* product without image_base64 field, the web component should use the image_url field as the image source.

**Validates: Requirements 3.4, 5.5**

### Property 11: Error continuation

*For any* product that fails image generation, the load script should continue processing subsequent products in the catalog.

**Validates: Requirements 5.4**

### Property 12: Fallback preservation

*For any* product where image generation fails after all retries, the indexed document should still contain the original image_url field.

**Validates: Requirements 5.2**

### Property 13: Skip existing images

*For any* product that already has image_base64 in OpenSearch, when regenerate flag is false, the system should skip image generation for that product.

**Validates: Requirements 7.3**

### Property 14: Image size validation

*For any* generated image, the size should be between 10KB and 500KB.

**Validates: Requirements 8.2**

### Property 15: Progress logging

*For any* product being processed, the system should emit a log entry containing the product name and current progress count.

**Validates: Requirements 4.2, 4.3**


## Error Handling

### Image Generation Failures

**Retry Strategy**:
- Maximum 3 retry attempts
- Exponential backoff: 1s, 2s, 4s
- Add jitter (±20%) to prevent thundering herd
- Log each retry attempt with error details

**Failure Modes**:
1. **Nova Canvas API Error**: Retry with backoff, log error, preserve image_url
2. **Throttling**: Implement exponential backoff with jitter
3. **Invalid Response**: Validate response, retry if invalid
4. **Timeout**: Set 30-second timeout per request, retry on timeout
5. **Network Error**: Retry with backoff, continue to next product if all retries fail

**Graceful Degradation**:
- Products without image_base64 fall back to image_url
- Load script continues processing even if some images fail
- Web component handles missing image_base64 gracefully

### Validation Errors

**Image Validation Checks**:
1. Response contains image data (non-empty)
2. Image size within bounds (10KB - 500KB)
3. Base64 encoding is valid (can be decoded)
4. PNG format signature present in decoded bytes

**Validation Failure Handling**:
- Log validation error with product ID
- Retry generation (counts toward retry limit)
- If all retries fail validation, skip image_base64 for that product
- Continue processing remaining products

### OpenSearch Errors

**Index Creation**:
- If index exists, verify mapping includes image_base64 field
- If mapping is incompatible, log error and exit
- Provide clear error message for resolution

**Document Indexing**:
- If document exceeds size limit, log error and skip image_base64
- Retry transient errors (network, throttling)
- Continue processing remaining products

## Testing Strategy

### Unit Tests

**Image Generation Module**:
- Test prompt generation with various product combinations
- Test base64 encoding/decoding round-trip
- Test image validation logic
- Test retry mechanism with mock API failures
- Test error handling for various failure modes

**Load Script**:
- Test command-line argument parsing
- Test skip/regenerate logic
- Test progress logging
- Test error continuation behavior

**Web Component**:
- Test data URI construction
- Test image source priority logic
- Test fallback behavior

### Property-Based Tests

**Framework**: Hypothesis (Python)

**Test Configuration**: Minimum 100 iterations per property

**Property Tests**:
1. **Prompt Completeness** (Property 1): Generate random products, verify all fields in prompt
2. **Prompt Styling** (Property 2): Generate random products, verify keywords present
3. **Base64 Round-Trip** (Property 4): Generate random byte arrays, verify encoding/decoding
4. **Base64 Format** (Property 5): Generate random images, verify no newlines in encoding
5. **Document Size** (Property 6): Generate random products with images, verify size < 1MB
6. **Data URI Format** (Property 8): Generate random base64 strings, verify URI format
7. **Image Source Priority** (Property 9): Generate products with both fields, verify priority
8. **Fallback Behavior** (Property 10): Generate products without image_base64, verify fallback
9. **Image Size Validation** (Property 14): Generate random images, verify size bounds

**Test Tagging**: Each property test must include a comment:
```python
# Feature: ai-generated-product-images, Property 1: Prompt completeness
```

### Integration Tests

**End-to-End Flow**:
1. Run load script with test products
2. Verify images generated and stored in OpenSearch
3. Query products via MCP tools
4. Verify web component renders data URIs correctly

**Failure Scenarios**:
1. Test with Nova Canvas API unavailable
2. Test with invalid product data
3. Test with existing image_base64 (skip behavior)
4. Test with regenerate flag

## Performance Considerations

### Image Generation

**Timing**:
- Nova Canvas generation: ~3-5 seconds per image
- 24 products: ~72-120 seconds total
- Parallel generation possible but requires rate limit management

**Rate Limits**:
- Bedrock Nova Canvas: Check current account limits
- Implement rate limiting if needed (e.g., 5 concurrent requests)

### Storage Impact

**OpenSearch Document Size**:
- Base product data: ~1-2KB
- Embedding vector: ~4KB
- Base64 image: ~65-130KB
- Total per product: ~70-136KB
- 24 products: ~1.7-3.3MB total

**Network Transfer**:
- Search results with 10 products: ~700KB-1.3MB
- Acceptable for modern networks
- Browser caches data URIs after first load

### Optimization Opportunities

**Future Enhancements**:
1. Parallel image generation with rate limiting
2. Image compression before base64 encoding
3. Lazy loading of images in web component
4. Progressive image generation (generate on-demand for new products)

## Dependencies

### AWS Services

- **Amazon Bedrock**: Nova Canvas model access
  - Model ID: `amazon.nova-canvas-v1:0`
  - Region: us-east-1 (or configured region)
  - Permissions: `bedrock:InvokeModel`

- **OpenSearch Serverless**: Existing collection
  - No changes to access policies needed
  - Index mapping update required

### Python Libraries

**New Dependencies** (add to `scripts/requirements.txt`):
```
boto3>=1.28.0  # Already present
pillow>=10.0.0  # For image validation (optional)
```

**Existing Dependencies**:
- boto3: Bedrock API calls
- opensearch-py: Index management
- base64: Standard library

### Configuration

**Environment Variables**:
- `OPENSEARCH_ENDPOINT`: Existing
- `AWS_REGION`: Existing
- `BEDROCK_MODEL_ID`: New (default: amazon.nova-canvas-v1:0)

**Command-Line Arguments**:
- `--skip-images`: Skip image generation
- `--regenerate-images`: Force regeneration
- `--image-width`: Image width (default: 512)
- `--image-height`: Image height (default: 512)
- `--model-id`: Nova Canvas model ID

## Deployment Considerations

### Backward Compatibility

- Existing products with image_url continue to work
- Web component handles both image_base64 and image_url
- No breaking changes to MCP tools or OpenSearch queries
- Gradual migration: can generate images incrementally

### Rollout Strategy

1. **Phase 1**: Deploy code changes (load script, web component)
2. **Phase 2**: Run load script with `--regenerate-images` to generate all images
3. **Phase 3**: Verify images display correctly in ChatGPT
4. **Phase 4**: Monitor performance and error rates

### Rollback Plan

- If issues arise, run load script with `--skip-images`
- Products fall back to image_url automatically
- No data loss (image_url preserved)
- Can regenerate images after fixing issues

## Security Considerations

### API Access

- Bedrock API calls use IAM credentials
- No sensitive data in image prompts
- Generated images are product photography (no PII)

### Data Storage

- Base64 images stored in OpenSearch (already secured)
- No additional security requirements
- Images are public product photography

### Input Validation

- Validate product data before prompt generation
- Sanitize product names/descriptions to prevent prompt injection
- Limit prompt length to prevent abuse

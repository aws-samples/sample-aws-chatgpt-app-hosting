# Image Validation Report

## Problem Statement

You suspected that the ChatGPT UI might be showing stock Unsplash images instead of the Nova Canvas generated images that were created during catalog loading.

## Investigation Results

### ✓ What We Found

1. **Nova Canvas images ARE being generated** - The deployment notes confirm "24 products with AI-generated images"

2. **Images ARE stored in OpenSearch** - The `load_catalog.py` script successfully:
   - Generates images using Amazon Bedrock Nova Canvas
   - Encodes them as base64
   - Stores them in the `image_base64` field in OpenSearch

3. **The problem is in the MCP server response** - The `format_product_for_response()` function in `mcp_server/tools.py` only returns these fields:
   ```python
   return {
       "product_id": product.get("product_id", ""),
       "name": product.get("name", ""),
       "description": product.get("description", ""),
       "origin": product.get("origin", ""),
       "roast_level": product.get("roast_level", ""),
       "flavor_profile": product.get("flavor_profile", []),
       "price": product.get("price", 0.0),
       "image_url": product.get("image_url", "")  # ← Only returns Unsplash URL
   }
   ```
   
   **It does NOT include `image_base64`!**

4. **The web component only receives `image_url`** - Since the MCP tools don't return `image_base64`, the web component (`mcp_server/web_component.html`) only has access to the Unsplash fallback URLs.

## Root Cause

The Nova Canvas generated images exist in OpenSearch but are being filtered out by the `format_product_for_response()` function before they reach the ChatGPT UI.

## Solution

### Step 1: Update `mcp_server/tools.py`

Modify the `format_product_for_response()` function to include `image_base64`:

```python
def format_product_for_response(product: Dict) -> Dict:
    """
    Format product for response, ensuring all required fields are present
    
    Args:
        product: Product document from OpenSearch
    
    Returns:
        Formatted product dictionary
    """
    formatted = {
        "product_id": product.get("product_id", ""),
        "name": product.get("name", ""),
        "description": product.get("description", ""),
        "origin": product.get("origin", ""),
        "roast_level": product.get("roast_level", ""),
        "flavor_profile": product.get("flavor_profile", []),
        "price": product.get("price", 0.0),
        "image_url": product.get("image_url", "")
    }
    
    # Include image_base64 if available (Nova Canvas generated images)
    if "image_base64" in product and product["image_base64"]:
        formatted["image_base64"] = product["image_base64"]
    
    return formatted
```

### Step 2: Update `mcp_server/web_component.html`

Modify the `createProductCard()` function to prefer `image_base64` over `image_url`:

```javascript
function createProductCard(product) {
    const flavorTags = (product.flavor_profile || [])
        .map(flavor => `<span class="flavor-tag">${escapeHtml(flavor)}</span>`)
        .join('');
    
    // Prefer image_base64 (Nova Canvas) over image_url (Unsplash fallback)
    let imageSrc = escapeHtml(product.image_url);
    if (product.image_base64) {
        imageSrc = `data:image/png;base64,${product.image_base64}`;
    }
    
    return `
        <div class="product-card" data-product-id="${escapeHtml(product.product_id)}">
            <img 
                class="product-image" 
                src="${imageSrc}" 
                alt="${escapeHtml(product.name)}"
                onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22400%22 height=%22300%22%3E%3Crect fill=%22%23f0f0f0%22 width=%22400%22 height=%22300%22/%3E%3Ctext fill=%22%23999%22 font-family=%22sans-serif%22 font-size=%2224%22 x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 dy=%22.3em%22%3E☕%3C/text%3E%3C/svg%3E'"
            />
            <div class="product-content">
                <div class="product-name">${escapeHtml(product.name)}</div>
                <div class="product-origin">${escapeHtml(product.origin)}</div>
                <div class="product-details">
                    <span class="detail-badge roast">${escapeHtml(product.roast_level)} roast</span>
                </div>
                <div class="flavor-profiles">
                    ${flavorTags}
                </div>
                <div class="product-price">$${product.price.toFixed(2)}</div>
            </div>
        </div>
    `;
}
```

### Step 3: Deploy the Changes

After making these changes, you'll need to:

1. Update both `mcp_server/` and `lambda/mcp_server/` directories (they should be kept in sync)
2. Redeploy the Lambda function:
   ```bash
   cd infrastructure
   cdk deploy
   ```

## Verification

After deploying, you can verify the fix by:

1. Opening ChatGPT and searching for coffee products
2. Inspecting the images in the UI - they should now show the Nova Canvas generated product images
3. Running the test script again:
   ```bash
   python3 scripts/test_mcp_image_response.py
   ```
   You should see: `✓ SUCCESS: image_base64 field IS present in response!`

## Files Created for Validation

- `scripts/validate_images.py` - Checks OpenSearch directly for image_base64 fields
- `scripts/test_mcp_image_response.py` - Tests what the MCP server returns
- `scripts/check_opensearch_images.sh` - Helper script for manual verification
- `IMAGE_VALIDATION_REPORT.md` - This report

## Summary

✓ Nova Canvas images ARE being generated and stored in OpenSearch  
✗ The MCP server is filtering them out before sending to ChatGPT  
→ Fix: Update `format_product_for_response()` and the web component to include and use `image_base64`

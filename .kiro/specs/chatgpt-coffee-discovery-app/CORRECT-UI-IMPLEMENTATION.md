# Correct ChatGPT UI Implementation

## Date: December 4, 2025

## The Right Way (According to Official Docs)

After reading the official ChatGPT Apps SDK documentation, here's the CORRECT way to implement UI components:

### Key Requirements

1. **MIME Type:** `text/html+skybridge` (not `text/html`)
2. **Resource Registration:** Register HTML template as MCP resource
3. **Tool Linking:** Link tools to template via `openai/outputTemplate` metadata
4. **Data Flow:** Tool returns `structuredContent` → ChatGPT passes to widget via `window.openai.toolOutput`
5. **Widget Runtime:** Widget reads from `window.openai` global object

### Architecture Flow

```
User asks question
   ↓
ChatGPT calls MCP tool
   ↓
Tool returns {
  content: [...],           // Text for conversation
  structuredContent: {...}  // Data for widget
}
   ↓
ChatGPT loads widget template (text/html+skybridge)
   ↓
Widget reads window.openai.toolOutput
   ↓
Widget renders products with images
```

## What We Fixed

### 1. MIME Type

**Before:**
```python
'mimeType': 'text/html'
```

**After:**
```python
'mimeType': 'text/html+skybridge'
```

This signals to ChatGPT that it's a sandboxed widget template, not regular HTML.

### 2. Resource Metadata

**Before:**
```python
'annotations': {
    'openai/widgetPrefersBorder': True
}
```

**After:**
```python
'_meta': {
    'openai/widgetPrefersBorder': True,
    'openai/widgetDomain': 'https://chatgpt.com',
    'openai/widgetCSP': {
        'connect_domains': ['https://chatgpt.com'],
        'resource_domains': ['https://*.oaistatic.com', 'https://images.unsplash.com']
    }
}
```

Added proper CSP rules to allow loading images from Unsplash.

### 3. Tool Response Structure

**Before:**
```python
# Tried to add resource blocks
content.append({
    'type': 'resource',
    'resource': {...}
})
```

**After:**
```python
# Return structuredContent at top level
response_result = {
    'content': content,
    'structuredContent': result['structuredContent']  # Widget reads this!
}
```

The widget accesses this via `window.openai.toolOutput`.

### 4. Tool Metadata

Tools already have correct metadata:
```python
'annotations': {
    'openai/outputTemplate': 'ui://widget/coffee-discovery.html'
}
```

This links the tool to the widget template.

## How It Works

### 1. Tool Registration

```python
{
    'name': 'search_products_tool',
    'description': '...',
    'inputSchema': {...},
    'annotations': {
        'openai/outputTemplate': 'ui://widget/coffee-discovery.html'  # Links to widget
    }
}
```

### 2. Resource Registration

```python
{
    'uri': 'ui://widget/coffee-discovery.html',
    'mimeType': 'text/html+skybridge',  # Key: skybridge MIME type
    'text': '<html>...</html>',
    '_meta': {
        'openai/widgetPrefersBorder': True,
        'openai/widgetDomain': 'https://chatgpt.com',
        'openai/widgetCSP': {
            'connect_domains': [...],
            'resource_domains': ['https://images.unsplash.com']  # Allow Unsplash images
        }
    }
}
```

### 3. Tool Response

```python
{
    'content': [
        {'type': 'text', 'text': 'Found 8 products...'}
    ],
    'structuredContent': {
        'products': [
            {
                'product_id': '...',
                'name': '...',
                'image_url': 'https://images.unsplash.com/...',
                ...
            }
        ]
    }
}
```

### 4. Widget Reads Data

```javascript
// Widget JavaScript
function loadInitialProducts() {
    if (window.openai && window.openai.toolOutput) {
        const products = window.openai.toolOutput.products || [];
        renderProducts(products);
    }
}

// Listen for updates
window.addEventListener('openai:set_globals', (event) => {
    const products = event.detail?.globals?.toolOutput?.products;
    renderProducts(products);
});
```

### 5. Widget Renders Products

```javascript
function renderProducts(products) {
    products.forEach(product => {
        // Create product card with image
        const img = document.createElement('img');
        img.src = product.image_url;  // Unsplash URL
        img.alt = product.name;
        // ... render rest of product
    });
}
```

## Expected Result

When user asks "I want a fruity light roast coffee":

1. ✅ ChatGPT calls `search_products_tool`
2. ✅ Tool returns products with image URLs in `structuredContent`
3. ✅ ChatGPT loads `ui://widget/coffee-discovery.html` template
4. ✅ Widget reads `window.openai.toolOutput.products`
5. ✅ Widget renders product grid with images from Unsplash
6. ✅ User sees visual product carousel with photos!

## CSP Configuration

The `openai/widgetCSP` allows:
- **connect_domains:** APIs the widget can fetch from
- **resource_domains:** Domains for images, fonts, etc.

We added `https://images.unsplash.com` to allow product images.

## Deployment

```bash
# Authenticate
mwinit

# Deploy
cd infrastructure
CDK_DOCKER=finch npx aws-cdk deploy --require-approval never
```

## Testing

1. Open ChatGPT with Coffee Discovery connector
2. Ask: "I want a fruity light roast coffee"
3. Expected: Widget appears with product grid showing images
4. Each product should display:
   - Product photo (from Unsplash)
   - Name, origin, roast level
   - Flavor profile
   - Price
   - Description

## Key Differences from Previous Attempts

| Aspect | Previous (Wrong) | Current (Correct) |
|--------|------------------|-------------------|
| MIME Type | `text/html` | `text/html+skybridge` |
| Metadata | `annotations` | `_meta` |
| Data Passing | Resource blocks | `structuredContent` |
| Image Loading | Markdown/ImageContent | HTML `<img>` tags |
| CSP | Not configured | Proper CSP with Unsplash |

## Why Previous Attempts Failed

1. **Markdown Images** - ChatGPT doesn't render markdown images in tool responses
2. **ImageContent Blocks** - ChatGPT's MCP doesn't support ImageContent type
3. **Wrong MIME Type** - `text/html` doesn't trigger widget runtime
4. **Missing CSP** - Images blocked without proper CSP configuration

## References

- [ChatGPT UI Guide](https://developers.openai.com/apps-sdk/build/chatgpt-ui)
- [MCP Server Setup](https://developers.openai.com/apps-sdk/build/mcp-server)
- [Apps SDK Examples](https://github.com/openai/openai-apps-sdk-examples)

## Status

- ✅ Code updated with correct implementation
- ✅ MIME type changed to `text/html+skybridge`
- ✅ CSP configured for Unsplash images
- ✅ `structuredContent` properly passed
- ⏳ Ready for deployment and testing

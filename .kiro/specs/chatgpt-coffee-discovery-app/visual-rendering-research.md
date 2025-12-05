# Visual Rendering Research - ChatGPT Apps SDK

## Date: December 4, 2025

## Research Question
How can we render visual GUI components (product carousel with images) in ChatGPT Apps using MCP?

## MCP Specification Findings

### Supported Content Types (from schema 2025-11-25)

1. **ImageContent**
   - Base64-encoded image data
   - Supports MIME types: image/png, image/jpeg, image/svg+xml, image/webp
   - Can be included directly in tool responses
   - Format:
     ```json
     {
       "type": "image",
       "data": "<base64-encoded-image>",
       "mimeType": "image/png"
     }
     ```

2. **EmbeddedResource**
   - Can embed text or blob resources directly in responses
   - Schema states: "It is up to the client how best to render embedded resources"
   - Format:
     ```json
     {
       "type": "resource",
       "resource": {
         "uri": "resource-uri",
         "mimeType": "text/html",
         "text": "<content>"
       }
     }
     ```

3. **TextContent**
   - Plain text or markdown
   - ChatGPT can render markdown formatting
   - Supports inline image URLs in markdown

### Current Implementation Issues

**Problem 1: HTML Widget Not Rendering**
- Current code returns resource reference with `text/html` MIME type
- ChatGPT is not fetching or rendering the HTML component
- The `window.openai` API and `text/html+skybridge` may not be fully supported

**Problem 2: Formatted Text Only**
- Fallback implementation uses emoji-rich text formatting
- No actual product images displayed
- Users cannot see product photography

## Recommended Solutions

### Solution 1: Return Image URLs in Structured Content (RECOMMENDED)
**Approach:** Return product data with image URLs that ChatGPT can render inline

**Pros:**
- Simple implementation
- ChatGPT can display images from URLs
- Works with existing product data (image_url field)
- No base64 encoding needed

**Cons:**
- Requires publicly accessible image URLs
- Limited control over layout

**Implementation:**
```python
{
    "content": [
        {
            "type": "text",
            "text": "Found 3 coffee products:"
        },
        {
            "type": "image",
            "data": "<url-or-base64>",
            "mimeType": "image/jpeg"
        }
    ]
}
```

### Solution 2: Markdown with Inline Images
**Approach:** Use markdown formatting with image syntax

**Pros:**
- Simple, no special MCP features needed
- ChatGPT renders markdown natively
- Can include multiple images

**Cons:**
- Limited layout control
- No interactive elements

**Implementation:**
```markdown
## Ethiopian Yirgacheffe Light Roast

![Product Image](https://example.com/coffee.jpg)

**Origin:** Ethiopia
**Roast:** Light
**Price:** $18.99
```

### Solution 3: Multiple ImageContent Blocks
**Approach:** Return each product image as a separate ImageContent block

**Pros:**
- Uses official MCP ImageContent type
- ChatGPT should render images natively
- Can include multiple products

**Cons:**
- May not create carousel layout
- Images might stack vertically

### Solution 4: Rich Text with Embedded Images
**Approach:** Combine text and image content blocks in sequence

**Pros:**
- Best of both worlds - text + images
- Uses standard MCP content types
- ChatGPT controls rendering

**Cons:**
- Layout determined by ChatGPT
- May not match desired design

## Recommendation

**Implement Solution 4: Rich Text with Embedded Images**

For each product, return:
1. Text block with product details
2. Image block with product photo
3. Repeat for each product

This approach:
- Uses standard MCP content types
- Lets ChatGPT handle rendering (they know their UI best)
- Provides visual product display with images
- Works within MCP specification
- No custom HTML/JavaScript needed

## Next Steps

1. Update `lambda/mcp_handler.py` to return ImageContent blocks
2. Update `mcp_server/tools.py` to format responses with images
3. Test in ChatGPT to verify images render
4. Iterate on formatting based on results

## References

- MCP Specification: https://github.com/modelcontextprotocol/specification
- Schema: https://raw.githubusercontent.com/modelcontextprotocol/specification/main/schema/2025-11-25/schema.json

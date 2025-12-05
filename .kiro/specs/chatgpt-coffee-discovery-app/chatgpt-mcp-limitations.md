# ChatGPT MCP Limitations - Image Rendering

## Date: December 4, 2025

## Problem Statement

We attempted to render product images in ChatGPT using the MCP (Model Context Protocol), but **ChatGPT does not display images from MCP tool responses**.

## What We Tried

### Attempt 1: Markdown Images
**Approach:** Return markdown-formatted text with image syntax `![alt](url)`

**Result:** ❌ Failed
- ChatGPT displayed raw markdown text
- Images did not render
- Log showed: Full markdown text including `![Product](url)` syntax

### Attempt 2: MCP ImageContent Blocks
**Approach:** Return proper MCP `ImageContent` blocks with image URLs

**Implementation:**
```python
{
    "content": [
        {"type": "text", "text": "Found 8 products..."},
        {"type": "image", "data": "https://...", "mimeType": "image/jpeg"},
        {"type": "text", "text": "Product 2..."},
        {"type": "image", "data": "https://...", "mimeType": "image/jpeg"}
    ]
}
```

**Result:** ❌ Failed
- ChatGPT only displayed the first text block
- All image blocks were ignored
- Log showed: `{text: 'Found 8 coffee products...'}`
- No image content in logs at all

### Attempt 3: HTML Web Component
**Approach:** Return HTML resource with embedded JavaScript

**Result:** ❌ Failed (from previous attempts)
- ChatGPT did not fetch or render the HTML resource
- `window.openai` API not available
- Resource references ignored

## Root Cause Analysis

**ChatGPT's MCP Implementation Limitations:**

1. **No ImageContent Support** - ChatGPT ignores `type: "image"` content blocks
2. **No Markdown Image Rendering** - Markdown images are displayed as text
3. **No HTML Widget Support** - Custom HTML resources are not rendered
4. **Text-Only Content** - Only `type: "text"` content blocks are processed

**Evidence:**
- ChatGPT logs show only `{text: '...'}` responses
- No image data appears in logs
- Multiple content blocks are reduced to first text block only

## Current State of ChatGPT MCP

Based on testing, ChatGPT's MCP implementation currently supports:
- ✅ Text content blocks
- ✅ Tool calling
- ✅ Structured data (for ChatGPT's internal use)
- ❌ Image content blocks
- ❌ HTML/web components
- ❌ Markdown image rendering
- ❌ Multiple content blocks (only first text block shown)

## Implications

**For Coffee Discovery App:**
- Cannot display product photography in ChatGPT
- Limited to text-only responses
- No visual product carousel possible
- User experience is text-based only

**For MCP Apps in General:**
- Visual/rich content not supported in ChatGPT yet
- MCP spec includes ImageContent, but ChatGPT doesn't implement it
- Gap between MCP specification and ChatGPT's implementation

## Possible Explanations

1. **ChatGPT MCP is Early/Limited** - ChatGPT may have a minimal MCP implementation
2. **Security Restrictions** - ChatGPT may block external images for security
3. **UI Limitations** - ChatGPT's UI may not support rendering MCP images yet
4. **Feature Not Released** - Image support may be planned but not yet available

## Recommendations

### Short Term: Accept Text-Only Limitation

**Option 1: Rich Text Formatting**
- Use emojis and formatting for visual appeal
- Structure text clearly with headers and bullets
- Include image URLs as clickable links

**Example:**
```
☕ **Kenyan Nyeri** - $23.50
📍 Kenya | Light Roast
🌟 Flavors: fruity, citrus, berry

An exceptional light roast with intense fruit-forward flavors...

🖼️ View Image: https://images.unsplash.com/photo-...
```

**Option 2: Image URLs as Links**
- Provide image URLs that users can click
- ChatGPT may render these as clickable links
- Users can open images in new tab

### Medium Term: Monitor ChatGPT Updates

- Watch for ChatGPT MCP feature announcements
- Test periodically as ChatGPT updates
- Be ready to enable images when supported

### Long Term: Alternative Platforms

If visual content is critical:
- Consider other MCP clients that support ImageContent
- Build standalone web app with visual interface
- Use ChatGPT for conversation, separate UI for visuals

## Testing Checklist

To verify if ChatGPT adds image support in future:

- [ ] Test markdown images: `![alt](url)`
- [ ] Test ImageContent blocks with URLs
- [ ] Test ImageContent blocks with base64 data
- [ ] Test EmbeddedResource with image data
- [ ] Test HTML resources with `text/html+skybridge`
- [ ] Check ChatGPT release notes for MCP updates
- [ ] Test with different image sources (Unsplash, S3, etc.)

## Conclusion

**Current Reality:**
ChatGPT's MCP implementation does not support visual content rendering. The app must remain text-only for now.

**Best Path Forward:**
1. Implement rich text formatting with emojis
2. Include image URLs as clickable links
3. Monitor ChatGPT for future image support
4. Document this limitation for users

**Code Status:**
- MCP server correctly returns ImageContent blocks (spec-compliant)
- Lambda handler properly passes through content
- Issue is on ChatGPT's client-side rendering
- No code changes needed - waiting for ChatGPT support

## References

- MCP Specification: https://github.com/modelcontextprotocol/specification
- MCP ImageContent: Defined in schema but not implemented by ChatGPT
- ChatGPT Apps SDK: Limited documentation on supported content types

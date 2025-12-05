# Fixed Widget Implementation

## Date: December 4, 2025

## Problem Solved

ChatGPT was not loading the widget despite our implementation. After analyzing the official working example from OpenAI's repository, we identified and fixed multiple critical issues.

## Key Changes Made

### 1. Added `_meta` to Tool Definitions (Critical!)

**Before:**
```python
'annotations': {
    'openai/outputTemplate': 'ui://widget/coffee-discovery.html',
    'openai/resultCanProduceWidget': True,
    'openai/widgetAccessible': True
}
```

**After:**
```python
'_meta': {
    'openai/outputTemplate': 'ui://widget/coffee-discovery.html',
    'openai/toolInvocation/invoking': 'Brewing your perfect coffee search...',
    'openai/toolInvocation/invoked': 'Found your perfect beans!',
    'openai/widgetAccessible': True,
    'openai/resultCanProduceWidget': True
},
'annotations': {
    'destructiveHint': False,
    'openWorldHint': False,
    'readOnlyHint': True
}
```

### 2. Added `title` Field to Tools

```python
{
    'name': 'search_products_tool',
    'title': 'Search Coffee Products',  # NEW!
    'description': '...',
    ...
}
```

### 3. Restored `structuredContent` in Tool Responses

**We were removing it - that was wrong!**

```python
return {
    "content": content_blocks,
    "structuredContent": {  # MUST HAVE BOTH!
        "products": formatted_products,
        "message": message
    }
}
```

### 4. Added `_meta` to Tool Responses

```python
response_result['_meta'] = {
    'openai/toolInvocation/invoking': 'Brewing your perfect coffee search...',
    'openai/toolInvocation/invoked': 'Found your perfect beans!'
}
```

### 5. Implemented `resources/templates/list` Handler

```python
elif jsonrpc_method == 'resources/templates/list':
    response_data = {
        'jsonrpc': '2.0',
        'result': {
            'resourceTemplates': [
                {
                    'uriTemplate': 'ui://widget/coffee-discovery.html',
                    'name': 'Coffee Discovery Widget',
                    'title': 'Coffee Discovery Widget',
                    'description': 'Interactive web component for displaying coffee products',
                    'mimeType': 'text/html+skybridge',
                    '_meta': widget_meta
                }
            ]
        },
        'id': jsonrpc_id
    }
```

### 6. Added `_meta` to Resources

```python
{
    'uri': 'ui://widget/coffee-discovery.html',
    'name': 'Coffee Discovery Widget',
    'title': 'Coffee Discovery Widget',  # NEW!
    'description': 'Interactive web component for displaying coffee products',
    'mimeType': 'text/html+skybridge',
    '_meta': widget_meta  # NEW!
}
```

### 7. Enhanced Resource Read Response

```python
widget_meta = {
    'openai/outputTemplate': 'ui://widget/coffee-discovery.html',
    'openai/widgetAccessible': True,
    'openai/resultCanProduceWidget': True,
    'openai/widgetPrefersBorder': True,
    'openai/widgetDomain': 'https://chatgpt.com',
    'openai/widgetCSP': {
        'connect_domains': ['https://chatgpt.com'],
        'resource_domains': ['https://*.oaistatic.com', 'https://images.unsplash.com']
    }
}
```

## What We Learned from the Working Example

### Critical Metadata Keys

1. **`openai/toolInvocation/invoking`** - Text shown while tool is running
2. **`openai/toolInvocation/invoked`** - Text shown when tool completes
3. **`openai/widgetAccessible`** - Marks widget as accessible
4. **`openai/resultCanProduceWidget`** - Indicates tool can produce widgets
5. **`openai/outputTemplate`** - Links tool to widget template

### Metadata Placement

- **Tools:** Use `_meta` (not `annotations`) for widget metadata
- **Resources:** Include `_meta` with widget configuration
- **Tool Responses:** Include `_meta` with invocation status
- **Annotations:** Separate field for tool hints (destructiveHint, etc.)

### Response Structure

Must return BOTH:
- `content` - Text for conversation
- `structuredContent` - Data for widget (accessed via `window.openai.toolOutput`)

## Expected Behavior Now

When a user asks "I want a fruity light roast coffee":

1. ✅ ChatGPT shows "Brewing your perfect coffee search..." (invoking)
2. ✅ Tool executes and returns data
3. ✅ ChatGPT shows "Found your perfect beans!" (invoked)
4. ✅ Widget iframe loads with our HTML
5. ✅ Widget reads `structuredContent` from `window.openai.toolOutput`
6. ✅ Widget renders product carousel with images from Unsplash
7. ✅ User sees visual product display!

## Testing Instructions

1. **Open ChatGPT** with the Coffee Discovery connector
2. **Ask:** "I want a fruity light roast coffee"
3. **Look for:**
   - Status messages ("Brewing your search..." → "Found your perfect beans!")
   - Widget iframe appearing below the response
   - Product carousel with images
   - Interactive product cards

4. **If widget still doesn't appear:**
   - Check browser console for errors
   - Verify connector is properly configured
   - Check if you need to enable developer mode in ChatGPT
   - Try refreshing the connector in ChatGPT settings

## Files Modified

1. **lambda/mcp_handler.py**
   - Updated `tools/list` with `_meta` and `title`
   - Added `resources/templates/list` handler
   - Updated `resources/list` with `_meta`
   - Enhanced `resources/read` with complete `_meta`
   - Added `_meta` to tool call responses
   - Restored `structuredContent` in responses

2. **mcp_server/tools.py**
   - Restored `structuredContent` in all tool functions
   - Kept BOTH `content` and `structuredContent`

## Deployment Status

- ✅ Code updated
- ✅ Deployed to AWS
- ✅ Ready for testing

## Next Steps

1. Test in ChatGPT
2. Verify widget loads and displays products
3. Check that images render from Unsplash
4. Test all three tools (search, details, refine)
5. Report results!

## References

- Working example: https://github.com/openai/openai-apps-sdk-examples/blob/main/pizzaz_server_python/main.py
- Analysis document: `.kiro/specs/chatgpt-coffee-discovery-app/WORKING-EXAMPLE-ANALYSIS.md`

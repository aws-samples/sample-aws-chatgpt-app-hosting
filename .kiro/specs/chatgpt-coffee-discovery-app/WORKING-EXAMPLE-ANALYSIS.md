# Working Example Analysis

## Date: December 4, 2025

## Source

Analyzed the official working example from:
https://github.com/openai/openai-apps-sdk-examples/blob/main/pizzaz_server_python/main.py

## Key Findings

### 1. They Return BOTH `content` AND `structuredContent`

```python
return types.ServerResult(
    types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=widget.response_text,  # Simple text like "Rendered a pizza map!"
            )
        ],
        structuredContent={"pizzaTopping": topping},  # Data for the widget
        _meta=meta,  # Metadata at the result level
    )
)
```

**We were removing `structuredContent` - that was wrong!**

### 2. They Use `_meta` at Multiple Levels

#### On Tools (in list_tools):
```python
_meta={
    "openai/outputTemplate": widget.template_uri,
    "openai/toolInvocation/invoking": widget.invoking,  # NEW!
    "openai/toolInvocation/invoked": widget.invoked,    # NEW!
    "openai/widgetAccessible": True,
    "openai/resultCanProduceWidget": True,
}
```

#### On Resources (in list_resources):
```python
types.Resource(
    name=widget.title,
    title=widget.title,
    uri=widget.template_uri,
    description=_resource_description(widget),
    mimeType=MIME_TYPE,  # "text/html+skybridge"
    _meta=_tool_meta(widget),  # Same metadata as tools
)
```

#### On Tool Response (in call_tool):
```python
_meta={
    "openai/toolInvocation/invoking": widget.invoking,
    "openai/toolInvocation/invoked": widget.invoked,
}
```

### 3. They Use Resource Templates

They implement `list_resource_templates()` in addition to `list_resources()`:

```python
@mcp._mcp_server.list_resource_templates()
async def _list_resource_templates() -> List[types.ResourceTemplate]:
    return [
        types.ResourceTemplate(
            name=widget.title,
            title=widget.title,
            uriTemplate=widget.template_uri,
            description=_resource_description(widget),
            mimeType=MIME_TYPE,
            _meta=_tool_meta(widget),
        )
        for widget in widgets
    ]
```

### 4. They Load Pre-Built HTML Files

```python
@lru_cache(maxsize=None)
def _load_widget_html(component_name: str) -> str:
    html_path = ASSETS_DIR / f"{component_name}.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf8")
    
    # Fallback to versioned files like "pizzaz-carousel-abc123.html"
    fallback_candidates = sorted(ASSETS_DIR.glob(f"{component_name}-*.html"))
    if fallback_candidates:
        return fallback_candidates[-1].read_text(encoding="utf8")
```

### 5. Tool Annotations

They include specific annotations to disable approval prompts:

```python
annotations={
    "destructiveHint": False,
    "openWorldHint": False,
    "readOnlyHint": True,
}
```

### 6. MIME Type

They use the exact same MIME type we're using:
```python
MIME_TYPE = "text/html+skybridge"
```

## What We're Missing

### Critical Issues:

1. ❌ **Missing `openai/toolInvocation/invoking` and `invoked` metadata**
   - These tell ChatGPT what to show while the tool is running
   - Example: "Hand-tossing a map" → "Served a fresh map"

2. ❌ **Not implementing `list_resource_templates()`**
   - This might be required for ChatGPT to discover widgets

3. ❌ **We removed `structuredContent`** (in our last attempt)
   - Should keep BOTH `content` and `structuredContent`

4. ❌ **Missing `_meta` on tool responses**
   - The response itself needs metadata, not just the tool definition

5. ❌ **Not using `title` field on tools**
   - They set both `name` and `title` on tools

### Minor Issues:

- Missing tool annotations (destructiveHint, etc.)
- Not caching HTML loading
- Different response structure

## Action Plan

### Step 1: Update Lambda Handler

Add support for:
- `list_resource_templates()` method
- `_meta` in tool responses
- `openai/toolInvocation/*` metadata

### Step 2: Update Tool Definitions

Add to each tool:
```python
{
    'name': 'search_products_tool',
    'title': 'Search Coffee Products',  # ADD THIS
    'description': '...',
    'inputSchema': {...},
    '_meta': {  # CHANGE FROM annotations
        'openai/outputTemplate': 'ui://widget/coffee-discovery.html',
        'openai/toolInvocation/invoking': 'Brewing your search...',  # ADD
        'openai/toolInvocation/invoked': 'Found your perfect beans!',  # ADD
        'openai/widgetAccessible': True,
        'openai/resultCanProduceWidget': True,
    },
    'annotations': {  # KEEP THESE SEPARATE
        'destructiveHint': False,
        'openWorldHint': False,
        'readOnlyHint': True,
    }
}
```

### Step 3: Update Tool Responses

Return BOTH content and structuredContent:
```python
{
    'content': [
        {'type': 'text', 'text': 'Found 8 products...'}
    ],
    'structuredContent': {
        'products': formatted_products,
        'message': message
    },
    '_meta': {
        'openai/toolInvocation/invoking': 'Brewing your search...',
        'openai/toolInvocation/invoked': 'Found your perfect beans!',
    }
}
```

### Step 4: Add Resource Templates Handler

Implement `resources/templates/list` method in Lambda handler.

## Expected Outcome

After these changes, ChatGPT should:
1. Show "Brewing your search..." while the tool runs
2. Show "Found your perfect beans!" when complete
3. Load the widget iframe with our HTML
4. Pass `structuredContent` to the widget via `window.openai.toolOutput`
5. Render the product carousel with images

## Next Steps

1. Implement these changes in our code
2. Deploy and test
3. Verify widget loads in ChatGPT
4. Debug any remaining issues

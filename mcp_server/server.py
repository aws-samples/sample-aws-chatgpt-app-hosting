"""
MCP Server for Coffee Discovery ChatGPT App
Main entry point for the FastMCP server
"""
import os
import logging
from typing import Optional, List, Dict
from mcp.server.fastmcp import FastMCP
from tools import search_products, get_product_details, refine_preferences
from cart_tools import (
    add_to_cart_tool,
    view_cart_tool,
    update_cart_quantity_tool,
    remove_from_cart_tool,
    clear_cart_tool
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

_cloudfront_domain_cache = None

def get_cloudfront_domain() -> str:
    """Get CloudFront domain from env var, SSM Parameter Store, or fallback"""
    global _cloudfront_domain_cache
    if _cloudfront_domain_cache is not None:
        return _cloudfront_domain_cache
    # Check env var first (fastest, no network call)
    domain = os.getenv("CLOUDFRONT_DOMAIN", "")
    if domain:
        logger.info(f"CloudFront domain from env: {domain}")
        _cloudfront_domain_cache = domain
        return domain
    # Fallback to SSM
    try:
        import boto3
        ssm = boto3.client('ssm', region_name=os.getenv("AWS_REGION", "us-east-1"))
        response = ssm.get_parameter(Name='/coffee/cloudfront/domain')
        domain = response['Parameter']['Value']
        logger.info(f"CloudFront domain from SSM: {domain}")
        _cloudfront_domain_cache = domain
        return domain
    except Exception as e:
        logger.warning(f"Could not fetch CloudFront domain from SSM: {e}")
        _cloudfront_domain_cache = "https://d1pgev4o24ymec.cloudfront.net"
        return _cloudfront_domain_cache

# Use hardcoded domain at import time for decorator metadata (no network call)
# Actual domain resolved lazily via get_cloudfront_domain() at request time
CLOUDFRONT_DOMAIN = os.getenv("CLOUDFRONT_DOMAIN", "https://d1pgev4o24ymec.cloudfront.net")

# Initialize FastMCP server
mcp = FastMCP(
    "Coffee Discovery",
    host="0.0.0.0",
    port=8000,
    stateless_http=True
)

# Register web components as MCP resources
@mcp.resource(
    uri="ui://widget/coffee-discovery.html",
    name="Coffee Discovery Widget",
    description="Interactive web component for displaying coffee products",
    mime_type="text/html+skybridge",
    meta={
        # Preferred (current) MCP Apps surface per OpenAI Plugin UI reference:
        # resourceDomains covers images/fonts/scripts/styles; connectDomains is
        # only for fetch/XHR (not needed for images).
        "ui": {
            "prefersBorder": True,
            "csp": {
                "connectDomains": ["https://chatgpt.com"],
                "resourceDomains": [
                    CLOUDFRONT_DOMAIN,
                    "https://*.cloudfront.net",
                    "https://*.oaistatic.com"
                ]
            }
        },
        # Legacy ChatGPT compatibility key (snake_case) — still honored.
        "openai/widgetPrefersBorder": True,
        "openai/widgetCSP": {
            "connect_domains": ["https://chatgpt.com"],
            "resource_domains": [
                CLOUDFRONT_DOMAIN,
                "https://*.cloudfront.net",
                "https://*.oaistatic.com"
            ]
        }
    }
)
def get_web_component() -> str:
    """
    Return the web component HTML content.
    
    Returns:
        HTML content of the web component
    """
    try:
        # Read the web component HTML file
        web_component_path = os.path.join(os.path.dirname(__file__), "web_component.html")
        with open(web_component_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load web component: {e}")
        raise

@mcp.resource(
    uri="ui://widget/cart.html",
    name="Shopping Cart Widget",
    description="Interactive web component for displaying shopping cart",
    mime_type="text/html+skybridge",
    meta={
        # Preferred (current) MCP Apps surface per OpenAI Plugin UI reference:
        # resourceDomains covers images/fonts/scripts/styles; connectDomains is
        # only for fetch/XHR (not needed for images).
        "ui": {
            "prefersBorder": True,
            "csp": {
                "connectDomains": ["https://chatgpt.com"],
                "resourceDomains": [
                    CLOUDFRONT_DOMAIN,
                    "https://*.cloudfront.net",
                    "https://*.oaistatic.com"
                ]
            }
        },
        # Legacy ChatGPT compatibility key (snake_case) — still honored.
        "openai/widgetPrefersBorder": True,
        "openai/widgetCSP": {
            "connect_domains": ["https://chatgpt.com"],
            "resource_domains": [
                CLOUDFRONT_DOMAIN,
                "https://*.cloudfront.net",
                "https://*.oaistatic.com"
            ]
        }
    }
)
def get_cart_component() -> str:
    """
    Return the cart web component HTML content.
    
    Returns:
        HTML content of the cart web component
    """
    try:
        # Read the cart component HTML file
        cart_component_path = os.path.join(os.path.dirname(__file__), "cart_component.html")
        with open(cart_component_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load cart component: {e}")
        raise

# Register MCP tools with OpenAI metadata

@mcp.tool(
    meta={
        "openai/outputTemplate": "ui://widget/coffee-discovery.html",
        "openai/toolInvocation/invoking": "Brewing your perfect coffee search...",
        "openai/toolInvocation/invoked": "Found your perfect beans!",
        "openai/widgetAccessible": True,
        "openai/resultCanProduceWidget": True,
        "openai/widgetCSP": {
            "resource_domains": [
                CLOUDFRONT_DOMAIN
            ]
        }
    },
    annotations={"readOnlyHint": True}
)
def search_products_tool(preferences: str, filters: Optional[Dict] = None):
    """
    Search for coffee products based on natural language preferences.
    
    Args:
        preferences: Natural language description of coffee preferences (e.g., "fruity light roast")
        filters: Optional filters with keys: origin, roast_level, price_range (tuple), flavor_profile
    
    Returns:
        Dictionary with products array and message

    Returns all matching products in a single call and renders them in the widget. Call once per user request; do not repeat the same search.
    """
    return search_products(preferences, filters)

@mcp.tool(
    meta={
        "openai/outputTemplate": "ui://widget/coffee-discovery.html",
        "openai/toolInvocation/invoking": "Fetching coffee details...",
        "openai/toolInvocation/invoked": "Here are the details!",
        "openai/widgetAccessible": True,
        "openai/resultCanProduceWidget": True,
        "openai/widgetCSP": {
            "resource_domains": [
                CLOUDFRONT_DOMAIN
            ]
        }
    },
    annotations={"readOnlyHint": True}
)
def get_product_details_tool(product_id: str):
    """
    Get detailed information about a specific coffee product.
    
    Args:
        product_id: Unique product identifier (e.g., "ethiopian-yirgacheffe-light")
    
    Returns:
        Dictionary with product details and message

    Returns all matching products in a single call and renders them in the widget. Call once per user request; do not repeat the same search.
    """
    return get_product_details(product_id)

@mcp.tool(
    meta={
        "openai/outputTemplate": "ui://widget/coffee-discovery.html",
        "openai/toolInvocation/invoking": "Refining your search...",
        "openai/toolInvocation/invoked": "Refined results ready!",
        "openai/widgetAccessible": True,
        "openai/resultCanProduceWidget": True,
        "openai/widgetCSP": {
            "resource_domains": [
                CLOUDFRONT_DOMAIN
            ]
        }
    },
    annotations={"readOnlyHint": True}
)
def refine_preferences_tool(
    exclude: Optional[List[str]] = None,
    similar_to: Optional[str] = None,
    filters: Optional[Dict] = None
):
    """
    Refine product search with exclusions and similarity matching.
    
    Args:
        exclude: List of attributes to exclude (e.g., ["dark", "Brazil"])
        similar_to: Product ID to find similar products
        filters: Optional filters with keys: origin, roast_level, price_range (tuple), flavor_profile
    
    Returns:
        Dictionary with refined products array and message

    Returns all matching products in a single call and renders them in the widget. Call once per user request; do not repeat the same search.
    """
    return refine_preferences(exclude, similar_to, filters)

# Register cart tools

@mcp.tool(
    meta={
        "openai/outputTemplate": "ui://widget/cart.html",
        "openai/toolInvocation/invoking": "Adding to cart...",
        "openai/toolInvocation/invoked": "Added to cart!",
        "openai/widgetAccessible": True,
        "openai/resultCanProduceWidget": True
    }
)
def add_to_cart(product_id: str, quantity: int = 1):
    """
    Add a coffee product to the shopping cart.
    
    Args:
        product_id: Unique product identifier (e.g., "ethiopian-yirgacheffe-light")
        quantity: Number of items to add (default: 1)
    
    Returns:
        Dictionary with updated cart contents and message
    """
    return add_to_cart_tool(product_id, quantity)

@mcp.tool(
    meta={
        "openai/outputTemplate": "ui://widget/cart.html",
        "openai/toolInvocation/invoking": "Loading cart...",
        "openai/toolInvocation/invoked": "Cart loaded!",
        "openai/widgetAccessible": True,
        "openai/resultCanProduceWidget": True
    },
    annotations={"readOnlyHint": True}
)
def view_cart():
    """
    View current shopping cart contents.
    
    Returns:
        Dictionary with cart items, totals, and message
    """
    return view_cart_tool()

@mcp.tool(
    meta={
        "openai/outputTemplate": "ui://widget/cart.html",
        "openai/toolInvocation/invoking": "Updating quantity...",
        "openai/toolInvocation/invoked": "Quantity updated!",
        "openai/widgetAccessible": True,
        "openai/resultCanProduceWidget": True
    }
)
def update_cart_quantity(product_id: str, quantity: int):
    """
    Update the quantity of an item in the cart.
    
    Args:
        product_id: Product identifier
        quantity: New quantity (0 to remove item)
    
    Returns:
        Dictionary with updated cart contents and message
    """
    return update_cart_quantity_tool(product_id, quantity)

@mcp.tool(
    meta={
        "openai/outputTemplate": "ui://widget/cart.html",
        "openai/toolInvocation/invoking": "Removing item...",
        "openai/toolInvocation/invoked": "Item removed!",
        "openai/widgetAccessible": True,
        "openai/resultCanProduceWidget": True
    }
)
def remove_from_cart(product_id: str):
    """
    Remove an item from the shopping cart.
    
    Args:
        product_id: Product identifier to remove
    
    Returns:
        Dictionary with updated cart contents and message
    """
    return remove_from_cart_tool(product_id)

@mcp.tool(
    meta={
        "openai/outputTemplate": "ui://widget/cart.html",
        "openai/toolInvocation/invoking": "Clearing cart...",
        "openai/toolInvocation/invoked": "Cart cleared!",
        "openai/widgetAccessible": True,
        "openai/resultCanProduceWidget": True
    },
    annotations={"destructiveHint": True}
)
def clear_cart():
    """
    Remove all items from the shopping cart.
    
    Returns:
        Dictionary with empty cart and confirmation message
    """
    return clear_cart_tool()

# Create ASGI app for HTTP transport (required for AgentCore)
app = mcp.streamable_http_app()

# Add CORS middleware
try:
    from starlette.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )
except Exception:
    pass

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Coffee Discovery MCP Server...")
    logger.info(f"Host: 0.0.0.0, Port: 8000")
    logger.info(f"Stateless HTTP: True")
    logger.info("Registered tools: search_products_tool, get_product_details_tool, refine_preferences_tool")
    logger.info("Registered cart tools: add_to_cart, view_cart, update_cart_quantity, remove_from_cart, clear_cart")
    logger.info("Registered resources: ui://widget/coffee-discovery.html, ui://widget/cart.html")
    uvicorn.run("server:app", host="0.0.0.0", port=8000)

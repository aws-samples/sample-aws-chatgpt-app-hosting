"""
MCP Server for Coffee Discovery ChatGPT App
Main entry point for the FastMCP server
"""
import os
import logging
from typing import Optional, List, Dict
from fastmcp import FastMCP
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
    annotations={
        "openai/widgetPrefersBorder": True
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
    annotations={
        "openai/widgetPrefersBorder": True
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
    annotations={
        "openai/outputTemplate": "ui://widget/coffee-discovery.html",
        "openai/widgetCSP": {
            "resource_domains": [
                os.environ.get("CLOUDFRONT_DOMAIN", "")
            ]
        }
    }
)
def search_products_tool(preferences: str, filters: Optional[Dict] = None) -> Dict:
    """
    Search for coffee products based on natural language preferences.
    
    Args:
        preferences: Natural language description of coffee preferences (e.g., "fruity light roast")
        filters: Optional filters with keys: origin, roast_level, price_range (tuple), flavor_profile
    
    Returns:
        Dictionary with products array and message
    """
    return search_products(preferences, filters)

@mcp.tool(
    annotations={
        "openai/outputTemplate": "ui://widget/coffee-discovery.html",
        "openai/widgetCSP": {
            "resource_domains": [
                os.environ.get("CLOUDFRONT_DOMAIN", "")
            ]
        }
    }
)
def get_product_details_tool(product_id: str) -> Dict:
    """
    Get detailed information about a specific coffee product.
    
    Args:
        product_id: Unique product identifier (e.g., "ethiopian-yirgacheffe-light")
    
    Returns:
        Dictionary with product details and message
    """
    return get_product_details(product_id)

@mcp.tool(
    annotations={
        "openai/outputTemplate": "ui://widget/coffee-discovery.html",
        "openai/widgetCSP": {
            "resource_domains": [
                os.environ.get("CLOUDFRONT_DOMAIN", "")
            ]
        }
    }
)
def refine_preferences_tool(
    exclude: Optional[List[str]] = None,
    similar_to: Optional[str] = None,
    filters: Optional[Dict] = None
) -> Dict:
    """
    Refine product search with exclusions and similarity matching.
    
    Args:
        exclude: List of attributes to exclude (e.g., ["dark", "Brazil"])
        similar_to: Product ID to find similar products
        filters: Optional filters with keys: origin, roast_level, price_range (tuple), flavor_profile
    
    Returns:
        Dictionary with refined products array and message
    """
    return refine_preferences(exclude, similar_to, filters)

# Register cart tools

@mcp.tool(
    annotations={
        "openai/outputTemplate": "ui://widget/cart.html"
    }
)
def add_to_cart(product_id: str, quantity: int = 1) -> Dict:
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
    annotations={
        "openai/outputTemplate": "ui://widget/cart.html"
    }
)
def view_cart() -> Dict:
    """
    View current shopping cart contents.
    
    Returns:
        Dictionary with cart items, totals, and message
    """
    return view_cart_tool()

@mcp.tool(
    annotations={
        "openai/outputTemplate": "ui://widget/cart.html"
    }
)
def update_cart_quantity(product_id: str, quantity: int) -> Dict:
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
    annotations={
        "openai/outputTemplate": "ui://widget/cart.html"
    }
)
def remove_from_cart(product_id: str) -> Dict:
    """
    Remove an item from the shopping cart.
    
    Args:
        product_id: Product identifier to remove
    
    Returns:
        Dictionary with updated cart contents and message
    """
    return remove_from_cart_tool(product_id)

@mcp.tool(
    annotations={
        "openai/outputTemplate": "ui://widget/cart.html"
    }
)
def clear_cart() -> Dict:
    """
    Remove all items from the shopping cart.
    
    Returns:
        Dictionary with empty cart and confirmation message
    """
    return clear_cart_tool()

if __name__ == "__main__":
    logger.info("Starting Coffee Discovery MCP Server...")
    mcp.run(transport="http", host="0.0.0.0", port=8000)

"""
MCP Server for Coffee Discovery ChatGPT App
Main entry point for the FastMCP server
"""
import os
import logging
from typing import Optional, List, Dict
from fastmcp import FastMCP
from tools import search_products, get_product_details, refine_preferences

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

# Register web component as MCP resource
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

# Register MCP tools with OpenAI metadata

@mcp.tool(
    annotations={
        "openai/outputTemplate": "ui://widget/coffee-discovery.html"
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
        "openai/outputTemplate": "ui://widget/coffee-discovery.html"
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
        "openai/outputTemplate": "ui://widget/coffee-discovery.html"
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

if __name__ == "__main__":
    logger.info("Starting Coffee Discovery MCP Server...")
    logger.info(f"Host: 0.0.0.0, Port: 8000")
    logger.info(f"Stateless HTTP: True")
    logger.info("Registered tools: search_products_tool, get_product_details_tool, refine_preferences_tool")
    logger.info("Registered resource: ui://widget/coffee-discovery.html")
    mcp.run()

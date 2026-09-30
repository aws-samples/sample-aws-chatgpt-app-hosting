"""
Cart Tools - MCP tool implementations for shopping cart operations
"""
import logging
import os
from typing import Dict, Optional
from mcp.types import CallToolResult, TextContent
from cart_manager import CartManager
from cart_repository import CartRepository
from opensearch_client import OpenSearchClient

logger = logging.getLogger(__name__)

# Global instances (initialized on cold start)
_cart_manager = None


def get_cart_manager() -> CartManager:
    """Get or create cart manager instance."""
    global _cart_manager
    
    if _cart_manager is None:
        # Initialize dependencies
        cart_repo = CartRepository()
        opensearch_endpoint = os.environ.get('OPENSEARCH_ENDPOINT')
        opensearch_client = OpenSearchClient(endpoint=opensearch_endpoint)
        
        _cart_manager = CartManager(cart_repo, opensearch_client)
        logger.info("Initialized cart manager")
    
    return _cart_manager


def get_user_id_from_context() -> str:
    """
    Extract user ID from MCP context.
    
    In production, this would extract from Mcp-Session-Id header.
    For now, we'll use a placeholder that can be overridden.
    
    Returns:
        User identifier
    """
    # TODO: Extract from MCP context headers when available
    # For now, return a default user ID for testing
    user_id = os.environ.get('MCP_SESSION_ID', 'default-user')
    return user_id


def add_to_cart_tool(product_id: str, quantity: int = 1, user_id: Optional[str] = None) -> Dict:
    """
    Add a coffee product to the shopping cart.
    
    Args:
        product_id: Unique product identifier (e.g., "ethiopian-yirgacheffe-light")
        quantity: Number of items to add (default: 1)
        user_id: Optional user identifier (extracted from context if not provided)
    
    Returns:
        Dictionary with updated cart contents and message
    """
    try:
        if user_id is None:
            user_id = get_user_id_from_context()
        
        manager = get_cart_manager()
        result = manager.add_to_cart(user_id, product_id, quantity)
        
        # Format response for MCP
        return format_cart_response(result)
        
    except Exception as e:
        logger.error(f"Error in add_to_cart_tool: {e}")
        return format_error_response("Unable to add item to cart. Please try again.")


def view_cart_tool(user_id: Optional[str] = None) -> Dict:
    """
    View current shopping cart contents.
    
    Args:
        user_id: Optional user identifier (extracted from context if not provided)
    
    Returns:
        Dictionary with cart items, totals, and message
    """
    try:
        if user_id is None:
            user_id = get_user_id_from_context()
        
        manager = get_cart_manager()
        result = manager.get_cart(user_id)
        
        # Format response for MCP
        return format_cart_response(result)
        
    except Exception as e:
        logger.error(f"Error in view_cart_tool: {e}")
        return format_error_response("Unable to retrieve cart. Please try again.")


def update_cart_quantity_tool(product_id: str, quantity: int, user_id: Optional[str] = None) -> Dict:
    """
    Update the quantity of an item in the cart.
    
    Args:
        product_id: Product identifier
        quantity: New quantity (0 to remove item)
        user_id: Optional user identifier (extracted from context if not provided)
    
    Returns:
        Dictionary with updated cart contents and message
    """
    try:
        if user_id is None:
            user_id = get_user_id_from_context()
        
        manager = get_cart_manager()
        result = manager.update_quantity(user_id, product_id, quantity)
        
        # Format response for MCP
        return format_cart_response(result)
        
    except Exception as e:
        logger.error(f"Error in update_cart_quantity_tool: {e}")
        return format_error_response("Unable to update cart. Please try again.")


def remove_from_cart_tool(product_id: str, user_id: Optional[str] = None) -> Dict:
    """
    Remove an item from the shopping cart.
    
    Args:
        product_id: Product identifier to remove
        user_id: Optional user identifier (extracted from context if not provided)
    
    Returns:
        Dictionary with updated cart contents and message
    """
    try:
        if user_id is None:
            user_id = get_user_id_from_context()
        
        manager = get_cart_manager()
        result = manager.remove_item(user_id, product_id)
        
        # Format response for MCP
        return format_cart_response(result)
        
    except Exception as e:
        logger.error(f"Error in remove_from_cart_tool: {e}")
        return format_error_response("Unable to remove item. Please try again.")


def clear_cart_tool(user_id: Optional[str] = None) -> Dict:
    """
    Remove all items from the shopping cart.
    
    Args:
        user_id: Optional user identifier (extracted from context if not provided)
    
    Returns:
        Dictionary with empty cart and confirmation message
    """
    try:
        if user_id is None:
            user_id = get_user_id_from_context()
        
        manager = get_cart_manager()
        result = manager.clear_cart(user_id)
        
        # Format response for MCP
        return format_cart_response(result)
        
    except Exception as e:
        logger.error(f"Error in clear_cart_tool: {e}")
        return format_error_response("Unable to clear cart. Please try again.")


def format_cart_response(cart_data: Dict) -> CallToolResult:
    """Format cart data as CallToolResult with structuredContent for widget rendering."""
    message = cart_data.get('message', '')
    is_error = cart_data.get('error', False)

    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        structuredContent={
            'cart': {
                'items': cart_data.get('items', []),
                'total_items': cart_data.get('total_items', 0),
                'total_price': cart_data.get('total_price', 0.0),
                'message': message,
                'error': is_error
            }
        },
        isError=is_error
    )


def format_error_response(message: str) -> CallToolResult:
    """Format error as CallToolResult."""
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        structuredContent={
            'cart': {
                'items': [],
                'total_items': 0,
                'total_price': 0.0,
                'message': message,
                'error': True
            }
        },
        isError=True
    )

"""
Cart Manager - Business logic layer for cart operations
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, UTC
from cart_repository import CartRepository
from opensearch_client import OpenSearchClient

logger = logging.getLogger(__name__)


class CartManager:
    """Manager for cart business logic and operations."""
    
    def __init__(self, cart_repo: CartRepository, opensearch_client: OpenSearchClient):
        """
        Initialize the cart manager.
        
        Args:
            cart_repo: Cart repository for data access
            opensearch_client: OpenSearch client for product lookups
        """
        self.cart_repo = cart_repo
        self.opensearch_client = opensearch_client
        logger.info("Initialized CartManager")
    
    def add_to_cart(self, user_id: str, product_id: str, quantity: int = 1) -> Dict:
        """
        Add product to cart.
        
        Args:
            user_id: User identifier
            product_id: Product identifier
            quantity: Quantity to add (default: 1)
            
        Returns:
            Formatted cart response with items, totals, and message
        """
        try:
            # Validate product exists
            product = self.opensearch_client.get_product_by_id(product_id)
            if not product:
                logger.warning(f"Product {product_id} not found")
                return {
                    "error": True,
                    "message": f"Product '{product_id}' not found in catalog",
                    "items": [],
                    "total_items": 0,
                    "total_price": 0.0
                }
            
            # Validate quantity
            if quantity <= 0:
                return {
                    "error": True,
                    "message": "Quantity must be a positive integer",
                    "items": [],
                    "total_items": 0,
                    "total_price": 0.0
                }
            
            # Get existing cart
            cart = self.cart_repo.get_cart(user_id)
            items = cart['items'] if cart else []
            
            # Check if product already in cart
            existing_item = None
            for item in items:
                if item['product_id'] == product_id:
                    existing_item = item
                    break
            
            if existing_item:
                # Increment quantity
                existing_item['quantity'] = int(existing_item['quantity']) + quantity
                message = f"Updated {product.get('name', product_id)} quantity to {existing_item['quantity']}"
            else:
                # Add new item
                items.append({
                    'product_id': product_id,
                    'quantity': quantity,
                    'added_at': datetime.now(UTC).isoformat()
                })
                message = f"Added {product.get('name', product_id)} to cart"
            
            # Save cart
            updated_at = datetime.now(UTC).isoformat()
            self.cart_repo.save_cart(user_id, items, updated_at)
            
            # Return enriched cart
            enriched_items = self._enrich_cart_items(items)
            totals = self._calculate_totals(enriched_items)
            
            return {
                "items": enriched_items,
                "total_items": totals['total_items'],
                "total_price": totals['total_price'],
                "message": message
            }
            
        except Exception as e:
            logger.error(f"Error adding to cart: {e}")
            return {
                "error": True,
                "message": "Unable to add item to cart. Please try again.",
                "items": [],
                "total_items": 0,
                "total_price": 0.0
            }
    
    def get_cart(self, user_id: str) -> Dict:
        """
        Get cart with enriched product details.
        
        Args:
            user_id: User identifier
            
        Returns:
            Formatted cart response with items, totals, and message
        """
        try:
            cart = self.cart_repo.get_cart(user_id)
            
            if not cart or not cart.get('items'):
                return {
                    "items": [],
                    "total_items": 0,
                    "total_price": 0.0,
                    "message": "Your cart is empty"
                }
            
            # Enrich items with product details
            enriched_items = self._enrich_cart_items(cart['items'])
            totals = self._calculate_totals(enriched_items)
            
            return {
                "items": enriched_items,
                "total_items": totals['total_items'],
                "total_price": totals['total_price'],
                "message": f"Your cart has {totals['total_items']} items"
            }
            
        except Exception as e:
            logger.error(f"Error getting cart: {e}")
            return {
                "error": True,
                "message": "Unable to retrieve cart. Please try again.",
                "items": [],
                "total_items": 0,
                "total_price": 0.0
            }
    
    def update_quantity(self, user_id: str, product_id: str, quantity: int) -> Dict:
        """
        Update item quantity (0 removes item).
        
        Args:
            user_id: User identifier
            product_id: Product identifier
            quantity: New quantity (0 to remove)
            
        Returns:
            Formatted cart response with items, totals, and message
        """
        try:
            # Validate quantity
            if quantity < 0:
                return {
                    "error": True,
                    "message": "Quantity must be non-negative",
                    "items": [],
                    "total_items": 0,
                    "total_price": 0.0
                }
            
            # Get existing cart
            cart = self.cart_repo.get_cart(user_id)
            if not cart or not cart.get('items'):
                return {
                    "error": True,
                    "message": "Your cart is empty",
                    "items": [],
                    "total_items": 0,
                    "total_price": 0.0
                }
            
            items = cart['items']
            
            # Find item
            item_found = False
            new_items = []
            for item in items:
                if item['product_id'] == product_id:
                    item_found = True
                    if quantity > 0:
                        # Update quantity
                        item['quantity'] = quantity
                        new_items.append(item)
                    # If quantity is 0, don't add to new_items (removes it)
                else:
                    new_items.append(item)
            
            if not item_found:
                return {
                    "error": True,
                    "message": f"Item '{product_id}' is not in your cart",
                    "items": self._enrich_cart_items(items),
                    "total_items": self._calculate_totals(self._enrich_cart_items(items))['total_items'],
                    "total_price": self._calculate_totals(self._enrich_cart_items(items))['total_price']
                }
            
            # Save updated cart
            updated_at = datetime.now(UTC).isoformat()
            self.cart_repo.save_cart(user_id, new_items, updated_at)
            
            # Return enriched cart
            enriched_items = self._enrich_cart_items(new_items)
            totals = self._calculate_totals(enriched_items)
            
            if quantity == 0:
                message = f"Removed item from cart"
            else:
                message = f"Updated quantity to {quantity}"
            
            return {
                "items": enriched_items,
                "total_items": totals['total_items'],
                "total_price": totals['total_price'],
                "message": message
            }
            
        except Exception as e:
            logger.error(f"Error updating quantity: {e}")
            return {
                "error": True,
                "message": "Unable to update cart. Please try again.",
                "items": [],
                "total_items": 0,
                "total_price": 0.0
            }
    
    def remove_item(self, user_id: str, product_id: str) -> Dict:
        """
        Remove item from cart.
        
        Args:
            user_id: User identifier
            product_id: Product identifier
            
        Returns:
            Formatted cart response with items, totals, and message
        """
        return self.update_quantity(user_id, product_id, 0)
    
    def clear_cart(self, user_id: str) -> Dict:
        """
        Remove all items from cart.
        
        Args:
            user_id: User identifier
            
        Returns:
            Formatted cart response with empty cart and confirmation
        """
        try:
            # Get existing cart to check if it's already empty
            cart = self.cart_repo.get_cart(user_id)
            
            if not cart or not cart.get('items'):
                return {
                    "items": [],
                    "total_items": 0,
                    "total_price": 0.0,
                    "message": "Your cart is already empty"
                }
            
            # Clear cart
            updated_at = datetime.now(UTC).isoformat()
            self.cart_repo.save_cart(user_id, [], updated_at)
            
            return {
                "items": [],
                "total_items": 0,
                "total_price": 0.0,
                "message": "Cart cleared successfully"
            }
            
        except Exception as e:
            logger.error(f"Error clearing cart: {e}")
            return {
                "error": True,
                "message": "Unable to clear cart. Please try again.",
                "items": [],
                "total_items": 0,
                "total_price": 0.0
            }
    
    def _enrich_cart_items(self, items: List[Dict]) -> List[Dict]:
        """
        Fetch product details from OpenSearch and merge with cart items.
        
        Args:
            items: List of cart items with product_id and quantity
            
        Returns:
            List of enriched cart items with product details
        """
        enriched_items = []
        
        for item in items:
            product_id = item['product_id']
            quantity = int(item.get('quantity', 1))
            
            # Fetch product details
            product = self.opensearch_client.get_product_by_id(product_id)
            
            if product:
                price = float(product.get('price', 0.0))
                enriched_item = {
                    'product_id': product_id,
                    'quantity': quantity,
                    'name': product.get('name', 'Unknown Product'),
                    'description': product.get('description', ''),
                    'origin': product.get('origin', ''),
                    'roast_level': product.get('roast_level', ''),
                    'flavor_profile': product.get('flavor_profile', []),
                    'price': price,
                    'image_url': product.get('image_url', ''),
                    'subtotal': round(price * quantity, 2)
                }
                enriched_items.append(enriched_item)
            else:
                # Product not found, include basic info
                logger.warning(f"Product {product_id} not found during enrichment")
                enriched_items.append({
                    'product_id': product_id,
                    'quantity': quantity,
                    'name': 'Product Not Found',
                    'description': '',
                    'origin': '',
                    'roast_level': '',
                    'flavor_profile': [],
                    'price': 0.0,
                    'image_url': '',
                    'subtotal': 0.0
                })
        
        return enriched_items
    
    def _calculate_totals(self, enriched_items: List[Dict]) -> Dict:
        """
        Calculate item count and total price.
        
        Args:
            enriched_items: List of enriched cart items
            
        Returns:
            Dictionary with total_items and total_price
        """
        total_items = sum(item['quantity'] for item in enriched_items)
        total_price = round(sum(item['subtotal'] for item in enriched_items), 2)
        
        return {
            'total_items': total_items,
            'total_price': total_price
        }

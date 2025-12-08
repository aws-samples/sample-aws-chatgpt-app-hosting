"""
Cart Repository - Data access layer for DynamoDB cart operations
"""
import os
import logging
from typing import Optional, Dict, List
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class CartRepository:
    """Repository for managing cart data in DynamoDB."""
    
    def __init__(self, table_name: Optional[str] = None, region: str = "us-east-1"):
        """
        Initialize the cart repository.
        
        Args:
            table_name: DynamoDB table name (defaults to env var or 'coffee-cart')
            region: AWS region
        """
        self.table_name = table_name or os.environ.get("DYNAMODB_CART_TABLE", "coffee-cart")
        self.region = region
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(self.table_name)
        logger.info(f"Initialized CartRepository with table: {self.table_name}")
    
    def get_cart(self, user_id: str) -> Optional[Dict]:
        """
        Retrieve cart for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Cart dictionary with user_id, items, and updated_at, or None if not found
        """
        try:
            response = self.table.get_item(Key={'user_id': user_id})
            cart = response.get('Item')
            
            if cart:
                logger.info(f"Retrieved cart for user {user_id} with {len(cart.get('items', []))} items")
            else:
                logger.info(f"No cart found for user {user_id}")
            
            return cart
        except ClientError as e:
            logger.error(f"Error retrieving cart for user {user_id}: {e}")
            raise
    
    def save_cart(self, user_id: str, items: List[Dict], updated_at: str) -> None:
        """
        Save or update cart for a user.
        
        Args:
            user_id: User identifier
            items: List of cart items with product_id, quantity, and added_at
            updated_at: ISO 8601 timestamp of last update
        """
        try:
            self.table.put_item(
                Item={
                    'user_id': user_id,
                    'items': items,
                    'updated_at': updated_at
                }
            )
            logger.info(f"Saved cart for user {user_id} with {len(items)} items")
        except ClientError as e:
            logger.error(f"Error saving cart for user {user_id}: {e}")
            raise
    
    def delete_cart(self, user_id: str) -> None:
        """
        Delete cart for a user.
        
        Args:
            user_id: User identifier
        """
        try:
            self.table.delete_item(Key={'user_id': user_id})
            logger.info(f"Deleted cart for user {user_id}")
        except ClientError as e:
            logger.error(f"Error deleting cart for user {user_id}: {e}")
            raise

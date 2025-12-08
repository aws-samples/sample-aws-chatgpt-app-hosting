"""
Property-based tests for cart repository
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, UTC
from decimal import Decimal
from cart_repository import CartRepository
from moto import mock_aws
import boto3


# Test strategies
user_ids = st.text(
    min_size=10,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='-_'
    )
)

product_ids = st.text(
    min_size=5,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=('Ll', 'Nd'),
        whitelist_characters='-'
    )
)

positive_quantities = st.integers(min_value=1, max_value=100)

@st.composite
def cart_item(draw):
    """Generate a cart item."""
    return {
        "product_id": draw(product_ids),
        "quantity": draw(positive_quantities),
        "added_at": datetime.now(UTC).isoformat()
    }

@st.composite
def cart_items_list(draw):
    """Generate a list of unique cart items."""
    items = draw(st.lists(
        cart_item(),
        min_size=0,
        max_size=20,
        unique_by=lambda x: x["product_id"]
    ))
    return items


@pytest.fixture
def dynamodb_table():
    """Create a mock DynamoDB table for testing."""
    with mock_aws():
        # Create DynamoDB resource
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        # Create table
        table = dynamodb.create_table(
            TableName='coffee-cart',
            KeySchema=[
                {'AttributeName': 'user_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'user_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        yield table


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, items=cart_items_list())
def test_cart_persistence(user_id, items):
    """
    **Feature: shopping-cart, Property 12: Cart modifications persist to DynamoDB**
    **Validates: Requirements 6.1, 6.3**
    
    For any cart modification operation, immediately querying DynamoDB for that user's cart
    should return the updated cart state.
    """
    with mock_aws():
        # Setup
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        dynamodb.create_table(
            TableName='coffee-cart',
            KeySchema=[{'AttributeName': 'user_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'user_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        
        repo = CartRepository(table_name='coffee-cart', region='us-east-1')
        updated_at = datetime.now(UTC).isoformat()
        
        # Act - save cart
        repo.save_cart(user_id, items, updated_at)
        
        # Assert - retrieve cart and verify it matches
        retrieved_cart = repo.get_cart(user_id)
        
        assert retrieved_cart is not None, "Cart should be persisted"
        assert retrieved_cart['user_id'] == user_id, "User ID should match"
        assert retrieved_cart['updated_at'] == updated_at, "Updated timestamp should match"
        assert len(retrieved_cart['items']) == len(items), "Number of items should match"
        
        # Verify each item
        for i, item in enumerate(items):
            assert retrieved_cart['items'][i]['product_id'] == item['product_id']
            assert retrieved_cart['items'][i]['quantity'] == item['quantity']
            assert retrieved_cart['items'][i]['added_at'] == item['added_at']


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, items=cart_items_list())
def test_cart_retrieval(user_id, items):
    """
    **Feature: shopping-cart, Property 13: Cart retrieval loads persisted state**
    **Validates: Requirements 6.2**
    
    For any user identifier with a persisted cart in DynamoDB, retrieving the cart should
    return the exact cart state that was persisted, with all items, quantities, and totals matching.
    """
    with mock_aws():
        # Setup
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        dynamodb.create_table(
            TableName='coffee-cart',
            KeySchema=[{'AttributeName': 'user_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'user_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        
        repo = CartRepository(table_name='coffee-cart', region='us-east-1')
        updated_at = datetime.now(UTC).isoformat()
        
        # Act - persist cart then retrieve it
        repo.save_cart(user_id, items, updated_at)
        retrieved_cart = repo.get_cart(user_id)
        
        # Assert - retrieved cart matches persisted state exactly
        assert retrieved_cart is not None
        assert retrieved_cart['user_id'] == user_id
        assert retrieved_cart['updated_at'] == updated_at
        assert retrieved_cart['items'] == items


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids)
def test_empty_cart_initialization(user_id):
    """
    **Feature: shopping-cart, Property 14: Non-existent carts initialize as empty**
    **Validates: Requirements 6.4**
    
    For any user identifier without a persisted cart in DynamoDB, retrieving the cart
    should return None (allowing the caller to initialize an empty cart).
    """
    with mock_aws():
        # Setup
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        dynamodb.create_table(
            TableName='coffee-cart',
            KeySchema=[{'AttributeName': 'user_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'user_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        
        repo = CartRepository(table_name='coffee-cart', region='us-east-1')
        
        # Act - retrieve cart for user that doesn't exist
        retrieved_cart = repo.get_cart(user_id)
        
        # Assert - should return None
        assert retrieved_cart is None, "Non-existent cart should return None"


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, items=cart_items_list())
def test_persisted_cart_schema(user_id, items):
    """
    **Feature: shopping-cart, Property 15: Persisted carts contain all required fields**
    **Validates: Requirements 6.5**
    
    For any cart persisted to DynamoDB, the stored record should contain user_id, items
    (with product_id and quantity for each), and updated_at timestamp.
    """
    with mock_aws():
        # Setup
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        dynamodb.create_table(
            TableName='coffee-cart',
            KeySchema=[{'AttributeName': 'user_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'user_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        
        repo = CartRepository(table_name='coffee-cart', region='us-east-1')
        updated_at = datetime.now(UTC).isoformat()
        
        # Act - save cart
        repo.save_cart(user_id, items, updated_at)
        retrieved_cart = repo.get_cart(user_id)
        
        # Assert - all required fields are present
        assert 'user_id' in retrieved_cart, "Cart must have user_id"
        assert 'items' in retrieved_cart, "Cart must have items"
        assert 'updated_at' in retrieved_cart, "Cart must have updated_at"
        
        # Assert - user_id is correct type
        assert isinstance(retrieved_cart['user_id'], str), "user_id must be string"
        
        # Assert - items is a list
        assert isinstance(retrieved_cart['items'], list), "items must be a list"
        
        # Assert - each item has required fields
        for item in retrieved_cart['items']:
            assert 'product_id' in item, "Each item must have product_id"
            assert 'quantity' in item, "Each item must have quantity"
            assert isinstance(item['product_id'], str), "product_id must be string"
            # DynamoDB returns Decimal for numbers
            assert isinstance(item['quantity'], (int, Decimal)), "quantity must be integer or Decimal"
            assert item['quantity'] > 0, "quantity must be positive"
        
        # Assert - updated_at is a string (ISO 8601 timestamp)
        assert isinstance(retrieved_cart['updated_at'], str), "updated_at must be string"


def test_cart_deletion():
    """Example-based test for cart deletion."""
    with mock_aws():
        # Setup
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        dynamodb.create_table(
            TableName='coffee-cart',
            KeySchema=[{'AttributeName': 'user_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'user_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        
        repo = CartRepository(table_name='coffee-cart', region='us-east-1')
        user_id = "test-user-123"
        items = [{"product_id": "test-product", "quantity": 1, "added_at": datetime.now(UTC).isoformat()}]
        updated_at = datetime.now(UTC).isoformat()
        
        # Save cart
        repo.save_cart(user_id, items, updated_at)
        assert repo.get_cart(user_id) is not None
        
        # Delete cart
        repo.delete_cart(user_id)
        
        # Verify deletion
        assert repo.get_cart(user_id) is None

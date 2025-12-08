"""
Property-based tests for cart manager
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, UTC
from decimal import Decimal
from cart_repository import CartRepository
from cart_manager import CartManager
from opensearch_client import OpenSearchClient
from moto import mock_aws
import boto3
from unittest.mock import Mock, MagicMock


# Test strategies
user_ids = st.text(
    min_size=10,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='-_'
    )
)

# Valid product IDs from the catalog
valid_product_ids = st.sampled_from([
    "ethiopian-yirgacheffe-light",
    "colombian-supremo-medium",
    "brazilian-santos-dark"
])

# Invalid product IDs
invalid_product_ids = st.text(
    min_size=5,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=('Ll', 'Nd'),
        whitelist_characters='-'
    )
).filter(lambda x: x not in [
    "ethiopian-yirgacheffe-light",
    "colombian-supremo-medium",
    "brazilian-santos-dark"
])

positive_quantities = st.integers(min_value=1, max_value=100)


def create_mock_opensearch_client():
    """Create a mock OpenSearch client with test products."""
    mock_client = Mock(spec=OpenSearchClient)
    
    # Mock product data
    products = {
        "ethiopian-yirgacheffe-light": {
            "product_id": "ethiopian-yirgacheffe-light",
            "name": "Ethiopian Yirgacheffe",
            "description": "A bright and floral light roast",
            "origin": "Ethiopia",
            "roast_level": "light",
            "flavor_profile": ["floral", "fruity", "citrus"],
            "price": 18.99,
            "image_url": "https://example.com/image.jpg"
        },
        "colombian-supremo-medium": {
            "product_id": "colombian-supremo-medium",
            "name": "Colombian Supremo",
            "description": "A classic medium roast",
            "origin": "Colombia",
            "roast_level": "medium",
            "flavor_profile": ["nutty", "chocolatey", "caramel"],
            "price": 15.99,
            "image_url": "https://example.com/image.jpg"
        },
        "brazilian-santos-dark": {
            "product_id": "brazilian-santos-dark",
            "name": "Brazilian Santos Dark",
            "description": "A bold dark roast",
            "origin": "Brazil",
            "roast_level": "dark",
            "flavor_profile": ["chocolatey", "nutty", "earthy"],
            "price": 14.50,
            "image_url": "https://example.com/image.jpg"
        }
    }
    
    def get_product_by_id(product_id):
        return products.get(product_id)
    
    mock_client.get_product_by_id = Mock(side_effect=get_product_by_id)
    
    return mock_client


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, product_id=valid_product_ids, quantity=positive_quantities)
def test_adding_new_products_creates_correct_items(user_id, product_id, quantity):
    """
    **Feature: shopping-cart, Property 1: Adding new products creates cart items with correct quantity**
    **Validates: Requirements 1.1, 1.3**
    
    For any valid product ID and positive quantity, when adding the product to an empty cart,
    the cart should contain exactly one item with that product ID and the specified quantity.
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
        opensearch_client = create_mock_opensearch_client()
        manager = CartManager(repo, opensearch_client)
        
        # Act - add product to empty cart
        result = manager.add_to_cart(user_id, product_id, quantity)
        
        # Assert - cart should have exactly one item
        assert 'error' not in result or not result['error'], "Should not return error"
        assert len(result['items']) == 1, "Cart should have exactly one item"
        assert result['items'][0]['product_id'] == product_id, "Product ID should match"
        assert result['items'][0]['quantity'] == quantity, "Quantity should match"
        assert result['total_items'] == quantity, "Total items should equal quantity"


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, product_id=valid_product_ids, 
       initial_quantity=positive_quantities, add_quantity=positive_quantities)
def test_adding_existing_products_increments_quantity(user_id, product_id, initial_quantity, add_quantity):
    """
    **Feature: shopping-cart, Property 2: Adding existing products increments quantity**
    **Validates: Requirements 1.2**
    
    For any cart containing a product, when adding that same product with quantity Q,
    the product's quantity in the cart should increase by Q.
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
        opensearch_client = create_mock_opensearch_client()
        manager = CartManager(repo, opensearch_client)
        
        # Act - add product twice
        manager.add_to_cart(user_id, product_id, initial_quantity)
        result = manager.add_to_cart(user_id, product_id, add_quantity)
        
        # Assert - quantity should be incremented
        assert 'error' not in result or not result['error'], "Should not return error"
        assert len(result['items']) == 1, "Cart should still have one item"
        assert result['items'][0]['product_id'] == product_id, "Product ID should match"
        expected_quantity = initial_quantity + add_quantity
        assert result['items'][0]['quantity'] == expected_quantity, f"Quantity should be {expected_quantity}"
        assert result['total_items'] == expected_quantity, "Total items should match"


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, product_id=invalid_product_ids, quantity=positive_quantities)
def test_invalid_product_rejection(user_id, product_id, quantity):
    """
    **Feature: shopping-cart, Property 4: Invalid product IDs are rejected**
    **Validates: Requirements 1.5, 9.2**
    
    For any product ID that does not exist in the Product Catalog, attempting to add it
    to the cart should return an error and leave the cart unchanged.
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
        opensearch_client = create_mock_opensearch_client()
        manager = CartManager(repo, opensearch_client)
        
        # Act - try to add invalid product
        result = manager.add_to_cart(user_id, product_id, quantity)
        
        # Assert - should return error
        assert result.get('error') == True, "Should return error for invalid product"
        assert 'not found' in result['message'].lower(), "Error message should mention product not found"
        assert len(result['items']) == 0, "Cart should remain empty"
        assert result['total_items'] == 0, "Total items should be 0"
        assert result['total_price'] == 0.0, "Total price should be 0"


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, product_ids=st.lists(valid_product_ids, min_size=1, max_size=5, unique=True),
       quantities=st.lists(positive_quantities, min_size=1, max_size=5))
def test_cart_totals_calculation(user_id, product_ids, quantities):
    """
    **Feature: shopping-cart, Property 5: Cart totals are calculated correctly**
    **Validates: Requirements 2.2, 2.3, 2.4**
    
    For any cart state, the total_items should equal the sum of all item quantities,
    the subtotal for each item should equal price × quantity, and the total_price
    should equal the sum of all subtotals.
    """
    # Ensure we have matching quantities for each product
    quantities = quantities[:len(product_ids)]
    if len(quantities) < len(product_ids):
        quantities.extend([1] * (len(product_ids) - len(quantities)))
    
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
        opensearch_client = create_mock_opensearch_client()
        manager = CartManager(repo, opensearch_client)
        
        # Act - add multiple products
        for product_id, quantity in zip(product_ids, quantities):
            manager.add_to_cart(user_id, product_id, quantity)
        
        result = manager.get_cart(user_id)
        
        # Assert - totals are calculated correctly
        expected_total_items = sum(quantities)
        assert result['total_items'] == expected_total_items, "Total items should match sum of quantities"
        
        # Verify each item's subtotal
        expected_total_price = 0.0
        for item in result['items']:
            expected_subtotal = round(item['price'] * item['quantity'], 2)
            assert item['subtotal'] == expected_subtotal, f"Subtotal should be {expected_subtotal}"
            expected_total_price += expected_subtotal
        
        expected_total_price = round(expected_total_price, 2)
        assert result['total_price'] == expected_total_price, f"Total price should be {expected_total_price}"


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, product_ids=st.lists(valid_product_ids, min_size=1, max_size=3, unique=True))
def test_cart_view_completeness(user_id, product_ids):
    """
    **Feature: shopping-cart, Property 6: Viewing cart returns all items with complete details**
    **Validates: Requirements 2.1**
    
    For any cart state, viewing the cart should return all items with all required fields:
    product_id, quantity, name, description, origin, roast_level, flavor_profile, price,
    image_url, and subtotal.
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
        opensearch_client = create_mock_opensearch_client()
        manager = CartManager(repo, opensearch_client)
        
        # Act - add products and view cart
        for product_id in product_ids:
            manager.add_to_cart(user_id, product_id, 1)
        
        result = manager.get_cart(user_id)
        
        # Assert - all items have complete details
        required_fields = [
            'product_id', 'quantity', 'name', 'description', 'origin',
            'roast_level', 'flavor_profile', 'price', 'image_url', 'subtotal'
        ]
        
        assert len(result['items']) == len(product_ids), "Should return all items"
        
        for item in result['items']:
            for field in required_fields:
                assert field in item, f"Item must have {field} field"
            
            # Verify types
            assert isinstance(item['product_id'], str)
            assert isinstance(item['quantity'], int)
            assert isinstance(item['name'], str)
            assert isinstance(item['description'], str)
            assert isinstance(item['origin'], str)
            assert isinstance(item['roast_level'], str)
            assert isinstance(item['flavor_profile'], list)
            assert isinstance(item['price'], float)
            assert isinstance(item['image_url'], str)
            assert isinstance(item['subtotal'], float)


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, product_id=valid_product_ids, 
       initial_quantity=positive_quantities, new_quantity=positive_quantities)
def test_quantity_updates(user_id, product_id, initial_quantity, new_quantity):
    """
    **Feature: shopping-cart, Property 7: Updating quantity to positive values changes quantity correctly**
    **Validates: Requirements 3.1**
    
    For any cart containing a product, when updating that product's quantity to a positive
    integer N, the cart should contain that product with quantity exactly N, and totals
    should be recalculated correctly.
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
        opensearch_client = create_mock_opensearch_client()
        manager = CartManager(repo, opensearch_client)
        
        # Act - add product then update quantity
        manager.add_to_cart(user_id, product_id, initial_quantity)
        result = manager.update_quantity(user_id, product_id, new_quantity)
        
        # Assert - quantity should be updated
        assert 'error' not in result or not result['error'], "Should not return error"
        assert len(result['items']) == 1, "Cart should have one item"
        assert result['items'][0]['product_id'] == product_id, "Product ID should match"
        assert result['items'][0]['quantity'] == new_quantity, f"Quantity should be {new_quantity}"
        assert result['total_items'] == new_quantity, "Total items should match new quantity"


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, product_id=valid_product_ids, quantity=positive_quantities)
def test_quantity_zero_removal(user_id, product_id, quantity):
    """
    **Feature: shopping-cart, Property 8: Updating quantity to zero removes the item**
    **Validates: Requirements 3.2**
    
    For any cart containing a product, when updating that product's quantity to 0,
    the product should be completely removed from the cart.
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
        opensearch_client = create_mock_opensearch_client()
        manager = CartManager(repo, opensearch_client)
        
        # Act - add product then update quantity to 0
        manager.add_to_cart(user_id, product_id, quantity)
        result = manager.update_quantity(user_id, product_id, 0)
        
        # Assert - item should be removed
        assert 'error' not in result or not result['error'], "Should not return error"
        assert len(result['items']) == 0, "Cart should be empty"
        assert result['total_items'] == 0, "Total items should be 0"
        assert result['total_price'] == 0.0, "Total price should be 0"


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, existing_product=valid_product_ids, non_existent_product=valid_product_ids)
def test_non_existent_item_operations(user_id, existing_product, non_existent_product):
    """
    **Feature: shopping-cart, Property 9: Operations on non-existent items return errors**
    **Validates: Requirements 3.3, 4.3**
    
    For any cart state and any product ID not in the cart, attempting to update or remove
    that product should return an error and leave the cart unchanged.
    """
    assume(existing_product != non_existent_product)
    
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
        opensearch_client = create_mock_opensearch_client()
        manager = CartManager(repo, opensearch_client)
        
        # Act - add one product, try to update/remove another
        manager.add_to_cart(user_id, existing_product, 1)
        result = manager.update_quantity(user_id, non_existent_product, 5)
        
        # Assert - should return error
        assert result.get('error') == True, "Should return error for non-existent item"
        assert 'not in your cart' in result['message'].lower(), "Error message should mention item not in cart"
        
        # Cart should still have the original item
        assert len(result['items']) == 1, "Cart should still have one item"
        assert result['items'][0]['product_id'] == existing_product, "Original item should remain"


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, product_id=valid_product_ids, quantity=positive_quantities)
def test_item_removal(user_id, product_id, quantity):
    """
    **Feature: shopping-cart, Property 10: Removing items deletes them from cart**
    **Validates: Requirements 4.1**
    
    For any cart containing a product, when removing that product, the cart should no
    longer contain that product, and totals should be recalculated correctly.
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
        opensearch_client = create_mock_opensearch_client()
        manager = CartManager(repo, opensearch_client)
        
        # Act - add product then remove it
        manager.add_to_cart(user_id, product_id, quantity)
        result = manager.remove_item(user_id, product_id)
        
        # Assert - item should be removed
        assert 'error' not in result or not result['error'], "Should not return error"
        assert len(result['items']) == 0, "Cart should be empty"
        assert result['total_items'] == 0, "Total items should be 0"
        assert result['total_price'] == 0.0, "Total price should be 0"


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, product_ids=st.lists(valid_product_ids, min_size=1, max_size=5, unique=True))
def test_cart_clearing(user_id, product_ids):
    """
    **Feature: shopping-cart, Property 11: Clearing cart removes all items**
    **Validates: Requirements 5.1, 5.2**
    
    For any cart state, when clearing the cart, the resulting cart should have zero items,
    total_items should be 0, and total_price should be 0.
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
        opensearch_client = create_mock_opensearch_client()
        manager = CartManager(repo, opensearch_client)
        
        # Act - add products then clear cart
        for product_id in product_ids:
            manager.add_to_cart(user_id, product_id, 1)
        
        result = manager.clear_cart(user_id)
        
        # Assert - cart should be empty
        assert 'error' not in result or not result['error'], "Should not return error"
        assert len(result['items']) == 0, "Cart should be empty"
        assert result['total_items'] == 0, "Total items should be 0"
        assert result['total_price'] == 0.0, "Total price should be 0"

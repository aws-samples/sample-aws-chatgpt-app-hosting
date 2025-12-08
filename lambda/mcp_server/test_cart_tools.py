"""
Property-based tests for cart tools
"""
import pytest
from hypothesis import given, strategies as st, settings
import cart_tools
from cart_repository import CartRepository
from cart_manager import CartManager
from opensearch_client import OpenSearchClient
from moto import mock_aws
import boto3
from unittest.mock import Mock, patch


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

# Invalid inputs for testing
empty_strings = st.just("")
negative_quantities = st.integers(max_value=-1)
zero_quantity = st.just(0)


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


def setup_test_environment():
    """Setup test environment with mocked cart manager."""
    # Create DynamoDB table
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    dynamodb.create_table(
        TableName='coffee-cart',
        KeySchema=[{'AttributeName': 'user_id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'user_id', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST'
    )
    
    # Create cart manager with mocked OpenSearch
    repo = CartRepository(table_name='coffee-cart', region='us-east-1')
    opensearch_client = create_mock_opensearch_client()
    manager = CartManager(repo, opensearch_client)
    
    # Patch the global cart manager
    cart_tools._cart_manager = manager
    
    return manager


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, quantity=negative_quantities)
def test_negative_quantity_rejection(user_id, quantity):
    """
    **Feature: shopping-cart, Property 16: Invalid inputs are rejected with descriptive errors**
    **Validates: Requirements 9.3**
    
    For any invalid input (negative quantities, empty product IDs, malformed data),
    the Cart System should reject the operation and return a descriptive error message
    without modifying the cart.
    """
    with mock_aws():
        # Setup
        setup_test_environment()
        
        # Act - try to add with negative quantity
        result = cart_tools.add_to_cart_tool("ethiopian-yirgacheffe-light", quantity, user_id)
        
        # Assert - should return error with descriptive message
        cart_data = result.get('structuredContent', {}).get('cart', {})
        assert cart_data.get('error') == True, "Should return error for negative quantity"
        assert 'positive' in cart_data['message'].lower(), "Error message should mention positive"
        assert len(cart_data['items']) == 0, "Cart should remain empty"
        assert cart_data['total_items'] == 0, "Total items should be 0"


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, product_id=valid_product_ids)
def test_empty_product_id_rejection(user_id, product_id):
    """
    **Feature: shopping-cart, Property 16: Invalid inputs are rejected with descriptive errors**
    **Validates: Requirements 9.3**
    
    Test that empty product IDs are rejected with descriptive errors.
    """
    with mock_aws():
        # Setup
        setup_test_environment()
        
        # First add a valid product
        cart_tools.add_to_cart_tool(product_id, 1, user_id)
        
        # Act - try to update with empty product ID
        result = cart_tools.update_cart_quantity_tool("", 5, user_id)
        
        # Assert - should return error
        cart_data = result.get('structuredContent', {}).get('cart', {})
        assert cart_data.get('error') == True, "Should return error for empty product ID"
        assert cart_data['message'], "Should have error message"
        
        # Original cart should be unchanged
        view_result = cart_tools.view_cart_tool(user_id)
        view_cart_data = view_result.get('structuredContent', {}).get('cart', {})
        assert len(view_cart_data['items']) == 1, "Original item should remain"
        assert view_cart_data['items'][0]['product_id'] == product_id, "Original product should be unchanged"


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, product_id=valid_product_ids, quantity=negative_quantities)
def test_update_negative_quantity_rejection(user_id, product_id, quantity):
    """
    **Feature: shopping-cart, Property 16: Invalid inputs are rejected with descriptive errors**
    **Validates: Requirements 9.3**
    
    Test that updating to negative quantities is rejected with descriptive errors.
    """
    with mock_aws():
        # Setup
        setup_test_environment()
        
        # First add a valid product
        cart_tools.add_to_cart_tool(product_id, 1, user_id)
        
        # Act - try to update with negative quantity
        result = cart_tools.update_cart_quantity_tool(product_id, quantity, user_id)
        
        # Assert - should return error with descriptive message
        cart_data = result.get('structuredContent', {}).get('cart', {})
        assert cart_data.get('error') == True, "Should return error for negative quantity"
        assert 'negative' in cart_data['message'].lower() or 'non-negative' in cart_data['message'].lower(), \
            "Error message should mention negative/non-negative"
        
        # Original cart should be unchanged
        view_result = cart_tools.view_cart_tool(user_id)
        view_cart_data = view_result.get('structuredContent', {}).get('cart', {})
        assert len(view_cart_data['items']) == 1, "Original item should remain"
        assert view_cart_data['items'][0]['quantity'] == 1, "Original quantity should be unchanged"



@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, product_id=valid_product_ids)
def test_infrastructure_error_handling(user_id, product_id):
    """
    **Feature: shopping-cart, Property 17: Infrastructure failures return user-friendly errors**
    **Validates: Requirements 9.1, 9.4**
    
    For any DynamoDB or OpenSearch operation failure, the Cart System should catch the error
    and return a user-friendly error message (not exposing internal details).
    """
    with mock_aws():
        # Setup
        manager = setup_test_environment()
        
        # Simulate DynamoDB failure by making save_cart raise an exception
        original_save = manager.cart_repo.save_cart
        def failing_save(*args, **kwargs):
            raise Exception("DynamoDB connection timeout")
        
        manager.cart_repo.save_cart = failing_save
        
        # Act - try to add to cart (which will fail on save)
        result = cart_tools.add_to_cart_tool(product_id, 1, user_id)
        
        # Assert - should return user-friendly error
        cart_data = result.get('structuredContent', {}).get('cart', {})
        assert cart_data.get('error') == True, "Should return error for infrastructure failure"
        assert 'unable' in cart_data['message'].lower() or 'try again' in cart_data['message'].lower(), \
            "Error message should be user-friendly"
        # Should NOT expose internal error details
        assert 'DynamoDB' not in cart_data['message'], "Should not expose internal details"
        assert 'timeout' not in cart_data['message'].lower(), "Should not expose internal details"
        
        # Restore original function
        manager.cart_repo.save_cart = original_save


@settings(max_examples=100, deadline=None)
@given(user_id=user_ids, product_id=valid_product_ids)
def test_opensearch_error_handling(user_id, product_id):
    """
    **Feature: shopping-cart, Property 17: Infrastructure failures return user-friendly errors**
    **Validates: Requirements 9.1, 9.4**
    
    Test that OpenSearch failures return user-friendly errors.
    """
    with mock_aws():
        # Setup
        manager = setup_test_environment()
        
        # Simulate OpenSearch failure
        def failing_get_product(*args, **kwargs):
            raise Exception("OpenSearch connection failed")
        
        manager.opensearch_client.get_product_by_id = failing_get_product
        
        # Act - try to add to cart (which will fail on product lookup)
        result = cart_tools.add_to_cart_tool(product_id, 1, user_id)
        
        # Assert - should return user-friendly error
        cart_data = result.get('structuredContent', {}).get('cart', {})
        assert cart_data.get('error') == True, "Should return error for infrastructure failure"
        assert 'unable' in cart_data['message'].lower() or 'try again' in cart_data['message'].lower(), \
            "Error message should be user-friendly"
        # Should NOT expose internal error details
        assert 'OpenSearch' not in cart_data['message'], "Should not expose internal details"
        assert 'connection' not in cart_data['message'].lower(), "Should not expose internal details"

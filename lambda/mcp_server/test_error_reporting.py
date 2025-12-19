"""
Property-based tests for error reporting consistency
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Dict, List
from unittest.mock import Mock, patch, MagicMock
import json
import sys
from pathlib import Path
from io import StringIO

# Add scripts directory to path to import load_catalog functions
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from load_catalog import (
    load_products_from_file,
    validate_product,
    setup_opensearch_client,
    create_index_if_not_exists,
    generate_embeddings_for_products,
    index_products
)


# Test strategies for generating various error scenarios
invalid_product_ids = st.one_of(
    st.just(""),  # Empty string
    st.just(None),  # None
    st.integers(),  # Wrong type
    st.lists(st.text())  # Wrong type
)

invalid_flavor_profiles = st.one_of(
    st.just("not-a-list"),  # String instead of list
    st.just(123),  # Number instead of list
    st.just(None),  # None
    st.dictionaries(st.text(), st.text())  # Dict instead of list
)

invalid_prices = st.one_of(
    st.just(-1.0),  # Negative price
    st.just(0.0),  # Zero price
    st.just("19.99"),  # String instead of number
    st.just(None),  # None
    st.floats(min_value=-1000, max_value=-0.01)  # Any negative
)

missing_field_names = st.sampled_from([
    'product_id', 'name', 'description', 'origin',
    'roast_level', 'flavor_profile', 'price', 'image_url'
])


def create_valid_product(product_id: str = "test-product") -> Dict:
    """Create a valid product for testing"""
    return {
        "product_id": product_id,
        "name": "Test Coffee",
        "description": "A delicious test coffee with rich flavor",
        "origin": "Ethiopia",
        "roast_level": "medium",
        "flavor_profile": ["fruity", "floral"],
        "price": 18.99,
        "image_url": "https://example.com/coffee.jpg"
    }


@settings(max_examples=100)
@given(
    invalid_id=invalid_product_ids
)
def test_error_reporting_invalid_product_id(invalid_id):
    """
    **Feature: chatgpt-coffee-discovery-app, Property 12: Error reporting consistency**
    **Validates: Requirements 8.7**
    
    For any error encountered by the load script, the system should output
    a clear error message and exit with a non-zero status code.
    
    This test verifies error reporting for invalid product IDs.
    """
    # Create product with invalid ID
    product = create_valid_product()
    product['product_id'] = invalid_id
    
    # Capture log output
    with patch('load_catalog.logger') as mock_logger:
        # Act - validate product
        is_valid = validate_product(product, 0)
        
        # Assert - validation should fail
        assert not is_valid, \
            f"Product with invalid ID {invalid_id} should fail validation"
        
        # Assert - error should be logged
        assert mock_logger.error.called, \
            "Error message should be logged for invalid product"
        
        # Assert - error message should be descriptive
        error_calls = mock_logger.error.call_args_list
        assert len(error_calls) > 0, "At least one error should be logged"
        
        # Check that error message contains useful information
        error_message = str(error_calls[0])
        assert 'product_id' in error_message.lower() or 'index 0' in error_message.lower(), \
            "Error message should mention the problematic field or product index"


@settings(max_examples=100)
@given(
    invalid_flavor=invalid_flavor_profiles
)
def test_error_reporting_invalid_flavor_profile(invalid_flavor):
    """
    Test error reporting for invalid flavor profile types
    
    For any invalid flavor profile, the system should report a clear error
    """
    # Create product with invalid flavor profile
    product = create_valid_product()
    product['flavor_profile'] = invalid_flavor
    
    # Capture log output
    with patch('load_catalog.logger') as mock_logger:
        # Act - validate product
        is_valid = validate_product(product, 0)
        
        # Assert - validation should fail
        assert not is_valid, \
            f"Product with invalid flavor_profile {type(invalid_flavor)} should fail validation"
        
        # Assert - error should be logged
        assert mock_logger.error.called, \
            "Error message should be logged for invalid flavor profile"
        
        # Assert - error message mentions flavor_profile
        error_calls = mock_logger.error.call_args_list
        error_message = str(error_calls[0])
        assert 'flavor_profile' in error_message.lower(), \
            "Error message should mention flavor_profile"


@settings(max_examples=100)
@given(
    invalid_price=invalid_prices
)
def test_error_reporting_invalid_price(invalid_price):
    """
    Test error reporting for invalid prices
    
    For any invalid price, the system should report a clear error
    """
    # Create product with invalid price
    product = create_valid_product()
    product['price'] = invalid_price
    
    # Capture log output
    with patch('load_catalog.logger') as mock_logger:
        # Act - validate product
        is_valid = validate_product(product, 0)
        
        # Assert - validation should fail
        assert not is_valid, \
            f"Product with invalid price {invalid_price} should fail validation"
        
        # Assert - error should be logged
        assert mock_logger.error.called, \
            "Error message should be logged for invalid price"
        
        # Assert - error message mentions price
        error_calls = mock_logger.error.call_args_list
        error_message = str(error_calls[0])
        assert 'price' in error_message.lower(), \
            "Error message should mention price"


@settings(max_examples=100)
@given(
    missing_field=missing_field_names
)
def test_error_reporting_missing_required_field(missing_field):
    """
    Test error reporting for missing required fields
    
    For any missing required field, the system should report a clear error
    """
    # Create product missing a required field
    product = create_valid_product()
    del product[missing_field]
    
    # Capture log output
    with patch('load_catalog.logger') as mock_logger:
        # Act - validate product
        is_valid = validate_product(product, 0)
        
        # Assert - validation should fail
        assert not is_valid, \
            f"Product missing {missing_field} should fail validation"
        
        # Assert - error should be logged
        assert mock_logger.error.called, \
            "Error message should be logged for missing field"
        
        # Assert - error message mentions the missing field
        error_calls = mock_logger.error.call_args_list
        error_message = str(error_calls[0])
        assert missing_field in error_message.lower(), \
            f"Error message should mention the missing field '{missing_field}'"


@settings(max_examples=50)
@given(
    num_invalid=st.integers(min_value=1, max_value=5),
    total_products=st.integers(min_value=2, max_value=10)
)
def test_error_reporting_multiple_invalid_products(num_invalid, total_products):
    """
    Test error reporting when multiple products are invalid
    
    For any set of products with multiple validation errors, all errors
    should be reported clearly
    """
    assume(num_invalid < total_products)
    
    # Create mix of valid and invalid products
    products = []
    invalid_indices = set()
    
    for i in range(total_products):
        if i < num_invalid:
            # Create invalid product (missing required field)
            product = create_valid_product(f"product-{i}")
            del product['name']  # Make it invalid
            products.append(product)
            invalid_indices.add(i)
        else:
            # Create valid product
            products.append(create_valid_product(f"product-{i}"))
    
    # Capture log output
    with patch('load_catalog.logger') as mock_logger:
        # Act - validate all products
        validation_results = []
        for i, product in enumerate(products):
            is_valid = validate_product(product, i)
            validation_results.append(is_valid)
        
        # Assert - correct number of failures
        num_failed = sum(1 for v in validation_results if not v)
        assert num_failed == num_invalid, \
            f"Should have {num_invalid} validation failures, got {num_failed}"
        
        # Assert - error logged for each invalid product
        assert mock_logger.error.call_count >= num_invalid, \
            f"Should log at least {num_invalid} errors, got {mock_logger.error.call_count}"
        
        # Assert - each error message is descriptive
        for call in mock_logger.error.call_args_list:
            error_message = str(call)
            # Error should mention either a field name or product index
            has_context = any(
                keyword in error_message.lower()
                for keyword in ['index', 'product', 'field', 'missing', 'invalid']
            )
            assert has_context, \
                "Error message should provide context about the error"


def test_error_reporting_file_not_found():
    """
    Test error reporting when products file doesn't exist
    
    Should raise FileNotFoundError with clear message
    """
    non_existent_file = "non_existent_file_12345.json"
    
    # Act & Assert - should raise FileNotFoundError
    with pytest.raises(FileNotFoundError) as exc_info:
        load_products_from_file(non_existent_file)
    
    # Assert - error message mentions the file
    error_message = str(exc_info.value)
    assert non_existent_file in error_message, \
        "Error message should mention the missing file"


def test_error_reporting_invalid_json():
    """
    Test error reporting when JSON file is malformed
    
    Should raise JSONDecodeError with clear message
    """
    # Create temporary invalid JSON file
    import tempfile
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{ invalid json content }")
        f.flush()  # Ensure data is written to disk
        temp_file = f.name
    
    try:
        # Act & Assert - should raise JSONDecodeError
        with pytest.raises(json.JSONDecodeError):
            load_products_from_file(temp_file)
    finally:
        # Cleanup
        Path(temp_file).unlink()


def test_error_reporting_missing_products_array():
    """
    Test error reporting when JSON doesn't contain 'products' array
    
    Should raise ValueError with clear message
    """
    import tempfile
    
    # Create temporary JSON file without 'products' key
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"items": []}, f)
        f.flush()  # Ensure data is written to disk
        temp_file = f.name
    
    try:
        # Act & Assert - should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            load_products_from_file(temp_file)
        
        # Assert - error message mentions 'products'
        error_message = str(exc_info.value)
        assert 'products' in error_message.lower(), \
            "Error message should mention missing 'products' array"
    finally:
        # Cleanup
        Path(temp_file).unlink()


def test_error_reporting_empty_products_array():
    """
    Test error reporting when products array is empty
    
    Should raise ValueError with clear message
    """
    import tempfile
    
    # Create temporary JSON file with empty products array
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"products": []}, f)
        f.flush()  # Ensure data is written to disk
        temp_file = f.name
    
    try:
        # Act & Assert - should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            load_products_from_file(temp_file)
        
        # Assert - error message mentions empty array
        error_message = str(exc_info.value)
        assert 'empty' in error_message.lower(), \
            "Error message should mention empty products array"
    finally:
        # Cleanup
        Path(temp_file).unlink()


def test_error_reporting_opensearch_connection_failure():
    """
    Test error reporting when OpenSearch connection fails
    
    Should raise exception with clear message
    """
    invalid_endpoint = "https://invalid-endpoint-12345.example.com"
    region = "us-west-2"
    
    # Mock boto3 to avoid actual AWS calls
    with patch('boto3.Session') as mock_session:
        mock_credentials = Mock()
        mock_credentials.access_key = "fake_key"
        mock_credentials.secret_key = "fake_secret"
        mock_credentials.token = None
        mock_session.return_value.get_credentials.return_value = mock_credentials
        
        # Mock OpenSearch to raise connection error
        with patch('opensearchpy.OpenSearch') as mock_opensearch:
            mock_opensearch.side_effect = Exception("Connection refused")
            
            # Act & Assert - should raise exception
            with pytest.raises(Exception) as exc_info:
                setup_opensearch_client(invalid_endpoint, region)
            
            # Assert - error message is descriptive
            error_message = str(exc_info.value)
            assert len(error_message) > 0, \
                "Error message should not be empty"


def test_error_reporting_index_creation_failure():
    """
    Test error reporting when index creation fails
    
    Should raise exception with clear message
    """
    mock_client = Mock()
    mock_client.indices.exists.return_value = False
    mock_client.indices.create.side_effect = Exception("Permission denied")
    
    index_name = "test-index"
    
    # Act & Assert - should raise exception
    with pytest.raises(Exception) as exc_info:
        create_index_if_not_exists(mock_client, index_name)
    
    # Assert - error message is descriptive
    error_message = str(exc_info.value)
    assert len(error_message) > 0, \
        "Error message should not be empty"


def test_error_reporting_embedding_generation_failure():
    """
    Test error reporting when embedding generation fails
    
    Should raise exception with clear message
    """
    products = [create_valid_product()]
    region = "us-west-2"
    
    # Mock embeddings generator to fail
    with patch('embeddings.EmbeddingsGenerator') as mock_gen_class:
        mock_gen = Mock()
        mock_gen.generate_embedding.side_effect = Exception("Bedrock API error: Throttling")
        mock_gen_class.return_value = mock_gen
        
        # Act & Assert - should raise exception
        with pytest.raises(Exception) as exc_info:
            generate_embeddings_for_products(products, region)
        
        # Assert - error message is descriptive
        error_message = str(exc_info.value)
        assert len(error_message) > 0, \
            "Error message should not be empty"


def test_error_reporting_indexing_failure():
    """
    Test error reporting when product indexing fails
    
    Should raise exception with clear message
    """
    mock_client = Mock()
    mock_client.index.side_effect = Exception("Index operation failed")
    
    products = [create_valid_product()]
    index_name = "test-index"
    
    # Act & Assert - should raise exception
    with pytest.raises(Exception) as exc_info:
        index_products(mock_client, index_name, products)
    
    # Assert - error message is descriptive
    error_message = str(exc_info.value)
    assert len(error_message) > 0, \
        "Error message should not be empty"


@settings(max_examples=50)
@given(
    error_type=st.sampled_from([
        'file_not_found',
        'invalid_json',
        'missing_products',
        'empty_products',
        'invalid_product'
    ])
)
def test_error_reporting_consistency_across_error_types(error_type):
    """
    Test that all error types produce consistent error reporting
    
    For any type of error, the system should:
    1. Provide a clear error message
    2. Include context about what went wrong
    3. Not crash silently
    """
    import tempfile
    
    error_occurred = False
    error_message = None
    
    try:
        if error_type == 'file_not_found':
            load_products_from_file("non_existent_file.json")
        
        elif error_type == 'invalid_json':
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write("{ invalid }")
                f.flush()  # Ensure data is written to disk
                temp_file = f.name
            try:
                load_products_from_file(temp_file)
            finally:
                Path(temp_file).unlink()
        
        elif error_type == 'missing_products':
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump({"items": []}, f)
                f.flush()  # Ensure data is written to disk
                temp_file = f.name
            try:
                load_products_from_file(temp_file)
            finally:
                Path(temp_file).unlink()
        
        elif error_type == 'empty_products':
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump({"products": []}, f)
                f.flush()  # Ensure data is written to disk
                temp_file = f.name
            try:
                load_products_from_file(temp_file)
            finally:
                Path(temp_file).unlink()
        
        elif error_type == 'invalid_product':
            product = create_valid_product()
            del product['name']
            with patch('load_catalog.logger') as mock_logger:
                is_valid = validate_product(product, 0)
                if not is_valid and mock_logger.error.called:
                    error_occurred = True
                    error_message = str(mock_logger.error.call_args_list[0])
    
    except Exception as e:
        error_occurred = True
        error_message = str(e)
    
    # Assert - an error should have occurred
    assert error_occurred, \
        f"Error should have been raised or logged for {error_type}"
    
    # Assert - error message should not be empty
    assert error_message is not None and len(error_message) > 0, \
        f"Error message should not be empty for {error_type}"
    
    # Assert - error message should be descriptive (more than just "Error")
    assert len(error_message) > 10, \
        f"Error message should be descriptive for {error_type}, got: {error_message}"


def test_error_reporting_examples():
    """Example-based tests for error reporting"""
    
    # Test 1: Invalid product ID
    product = create_valid_product()
    product['product_id'] = ""
    
    with patch('load_catalog.logger') as mock_logger:
        is_valid = validate_product(product, 0)
        assert not is_valid
        assert mock_logger.error.called
    
    # Test 2: Missing required field
    product = create_valid_product()
    del product['origin']
    
    with patch('load_catalog.logger') as mock_logger:
        is_valid = validate_product(product, 0)
        assert not is_valid
        assert mock_logger.error.called
        error_message = str(mock_logger.error.call_args_list[0])
        assert 'origin' in error_message.lower()
    
    # Test 3: Invalid price
    product = create_valid_product()
    product['price'] = -10.0
    
    with patch('load_catalog.logger') as mock_logger:
        is_valid = validate_product(product, 0)
        assert not is_valid
        assert mock_logger.error.called
        error_message = str(mock_logger.error.call_args_list[0])
        assert 'price' in error_message.lower()
    
    # Test 4: Invalid flavor profile type
    product = create_valid_product()
    product['flavor_profile'] = "fruity"  # Should be a list
    
    with patch('load_catalog.logger') as mock_logger:
        is_valid = validate_product(product, 0)
        assert not is_valid
        assert mock_logger.error.called
        error_message = str(mock_logger.error.call_args_list[0])
        assert 'flavor_profile' in error_message.lower()

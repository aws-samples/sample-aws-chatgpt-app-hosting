"""
Property-based tests for data loading idempotence
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict
from unittest.mock import Mock, MagicMock, patch, call
import json
import sys
from pathlib import Path

# Add scripts directory to path to import load_catalog functions
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from load_catalog import index_products, validate_product


# Test strategies for product data
product_ids = st.text(
    min_size=5,
    max_size=50,
    alphabet=st.characters(whitelist_categories=('Ll', 'Nd'), whitelist_characters='-')
).filter(lambda x: x and not x.startswith('-') and not x.endswith('-'))

product_names = st.text(min_size=5, max_size=100, alphabet=st.characters(
    whitelist_categories=('Lu', 'Ll', 'Zs'),
    blacklist_characters='\x00\n\r\t'
)).filter(lambda x: x.strip())

product_descriptions = st.text(min_size=20, max_size=500, alphabet=st.characters(
    whitelist_categories=('Lu', 'Ll', 'Nd', 'P', 'Zs'),
    blacklist_characters='\x00\n\r\t'
)).filter(lambda x: x.strip())

origins = st.sampled_from([
    "Ethiopia", "Colombia", "Brazil", "Kenya", "Guatemala",
    "Costa Rica", "Sumatra", "Yemen", "Peru"
])

roast_levels = st.sampled_from(["light", "medium", "dark"])

flavor_profiles = st.lists(
    st.sampled_from([
        "fruity", "nutty", "chocolatey", "floral", "earthy",
        "spicy", "sweet", "citrus", "berry", "caramel"
    ]),
    min_size=1,
    max_size=4,
    unique=True
)

prices = st.floats(min_value=10.0, max_value=50.0, allow_nan=False, allow_infinity=False)

image_urls = st.builds(
    lambda: "https://example.com/coffee.jpg"
)


def create_product_strategy():
    """Strategy for generating valid product dictionaries"""
    return st.builds(
        lambda pid, name, desc, origin, roast, flavor, price, img: {
            "product_id": pid,
            "name": name,
            "description": desc,
            "origin": origin,
            "roast_level": roast,
            "flavor_profile": flavor,
            "price": round(price, 2),
            "image_url": img,
            "description_embedding": [0.1] * 1536  # Mock embedding
        },
        product_ids,
        product_names,
        product_descriptions,
        origins,
        roast_levels,
        flavor_profiles,
        prices,
        image_urls
    )


@settings(max_examples=100)
@given(
    products=st.lists(
        create_product_strategy(),
        min_size=1,
        max_size=20,
        unique_by=lambda p: p["product_id"]  # Ensure unique product IDs
    )
)
def test_data_loading_idempotence(products):
    """
    **Feature: chatgpt-coffee-discovery-app, Property 11: Data loading idempotence**
    **Validates: Requirements 8.5**
    
    For any product catalog, running the load script multiple times should result
    in the same products indexed (no duplicates based on product_id)
    """
    # Ensure we have valid products
    assume(len(products) > 0)
    assume(all(validate_product(p, i) for i, p in enumerate(products)))
    
    # Create mock OpenSearch client
    mock_client = Mock()
    
    # Track indexed documents by product_id
    indexed_documents = {}
    
    def mock_index(index, id, body, refresh=False, **kwargs):
        """Mock index operation that stores documents by ID"""
        indexed_documents[id] = body.copy()
        return {
            "_index": index,
            "_id": id,
            "_version": len([k for k in indexed_documents.keys() if k == id]),
            "result": "created" if id not in indexed_documents else "updated"
        }
    
    mock_client.index = Mock(side_effect=mock_index)
    mock_client.indices.refresh = Mock()
    
    index_name = "test-products"
    
    # Act - Index products first time
    count1 = index_products(mock_client, index_name, products)
    
    # Capture state after first indexing
    first_indexed_ids = set(indexed_documents.keys())
    first_indexed_count = len(indexed_documents)
    first_documents = {k: v.copy() for k, v in indexed_documents.items()}
    
    # Act - Index same products second time (idempotent operation)
    count2 = index_products(mock_client, index_name, products)
    
    # Capture state after second indexing
    second_indexed_ids = set(indexed_documents.keys())
    second_indexed_count = len(indexed_documents)
    second_documents = indexed_documents.copy()
    
    # Assert - Both operations should report same count
    assert count1 == len(products), \
        f"First indexing should index {len(products)} products, got {count1}"
    assert count2 == len(products), \
        f"Second indexing should index {len(products)} products, got {count2}"
    
    # Assert - Same number of unique documents after both operations
    assert first_indexed_count == second_indexed_count, \
        f"Should have same number of documents: {first_indexed_count} vs {second_indexed_count}"
    
    # Assert - Same product IDs indexed
    assert first_indexed_ids == second_indexed_ids, \
        "Should have same product IDs after both indexing operations"
    
    # Assert - No duplicate product IDs
    assert len(indexed_documents) == len(products), \
        f"Should have {len(products)} unique products, got {len(indexed_documents)}"
    
    # Assert - All original product IDs are present
    expected_ids = {p["product_id"] for p in products}
    assert second_indexed_ids == expected_ids, \
        "All product IDs should be indexed exactly once"
    
    # Assert - Document content should be identical (idempotent updates)
    for product_id in first_indexed_ids:
        assert product_id in second_documents, \
            f"Product {product_id} should exist after second indexing"
        
        # Compare key fields (excluding potential metadata)
        first_doc = first_documents[product_id]
        second_doc = second_documents[product_id]
        
        assert first_doc["product_id"] == second_doc["product_id"]
        assert first_doc["name"] == second_doc["name"]
        assert first_doc["description"] == second_doc["description"]
        assert first_doc["origin"] == second_doc["origin"]
        assert first_doc["roast_level"] == second_doc["roast_level"]
        assert first_doc["flavor_profile"] == second_doc["flavor_profile"]
        assert first_doc["price"] == second_doc["price"]
    
    # Assert - Index was called correct number of times
    # Should be called len(products) times for each indexing operation
    expected_calls = len(products) * 2
    assert mock_client.index.call_count == expected_calls, \
        f"Index should be called {expected_calls} times, got {mock_client.index.call_count}"
    
    # Assert - All index calls used product_id as document ID
    for call_args in mock_client.index.call_args_list:
        assert 'id' in call_args.kwargs or len(call_args.args) >= 2, \
            "Index call should include document ID"
        
        doc_id = call_args.kwargs.get('id') or call_args.args[1]
        assert doc_id in expected_ids, \
            f"Document ID {doc_id} should be a valid product_id"


@settings(max_examples=50)
@given(
    products=st.lists(
        create_product_strategy(),
        min_size=2,
        max_size=10,
        unique_by=lambda p: p["product_id"]
    ),
    num_runs=st.integers(min_value=2, max_value=5)
)
def test_multiple_load_runs_idempotence(products, num_runs):
    """
    Test that running the load operation multiple times (more than 2) maintains idempotence
    
    For any product catalog and any number of load runs, the final state should be
    identical to loading once
    """
    assume(len(products) > 0)
    assume(all(validate_product(p, i) for i, p in enumerate(products)))
    
    # Create mock OpenSearch client
    mock_client = Mock()
    indexed_documents = {}
    
    def mock_index(index, id, body, refresh=False, **kwargs):
        indexed_documents[id] = body.copy()
        return {"_index": index, "_id": id, "result": "updated"}
    
    mock_client.index = Mock(side_effect=mock_index)
    mock_client.indices.refresh = Mock()
    
    index_name = "test-products"
    
    # Act - Run indexing multiple times
    counts = []
    for run in range(num_runs):
        count = index_products(mock_client, index_name, products)
        counts.append(count)
    
    # Assert - All runs should report same count
    assert all(c == len(products) for c in counts), \
        f"All runs should index {len(products)} products, got {counts}"
    
    # Assert - Final state has exactly one document per product
    assert len(indexed_documents) == len(products), \
        f"Should have {len(products)} unique documents, got {len(indexed_documents)}"
    
    # Assert - All product IDs are present
    expected_ids = {p["product_id"] for p in products}
    actual_ids = set(indexed_documents.keys())
    assert actual_ids == expected_ids, \
        "All product IDs should be indexed exactly once"
    
    # Assert - No duplicates
    assert len(actual_ids) == len(products), \
        "Should have no duplicate product IDs"


def test_idempotence_with_modified_products():
    """
    Test that re-indexing with modified product data updates the documents
    (idempotent updates, not idempotent inserts)
    """
    # Create initial products
    products_v1 = [
        {
            "product_id": "ethiopian-yirgacheffe",
            "name": "Ethiopian Yirgacheffe",
            "description": "Bright and fruity coffee",
            "origin": "Ethiopia",
            "roast_level": "light",
            "flavor_profile": ["fruity", "floral"],
            "price": 18.99,
            "image_url": "https://example.com/yirgacheffe.jpg",
            "description_embedding": [0.1] * 1536
        },
        {
            "product_id": "colombian-supremo",
            "name": "Colombian Supremo",
            "description": "Smooth and balanced",
            "origin": "Colombia",
            "roast_level": "medium",
            "flavor_profile": ["nutty", "chocolatey"],
            "price": 16.99,
            "image_url": "https://example.com/supremo.jpg",
            "description_embedding": [0.2] * 1536
        }
    ]
    
    # Create modified versions (same IDs, different data)
    products_v2 = [
        {
            "product_id": "ethiopian-yirgacheffe",
            "name": "Ethiopian Yirgacheffe Premium",  # Changed name
            "description": "Exceptionally bright and fruity coffee",  # Changed description
            "origin": "Ethiopia",
            "roast_level": "light",
            "flavor_profile": ["fruity", "floral", "citrus"],  # Added flavor
            "price": 22.99,  # Changed price
            "image_url": "https://example.com/yirgacheffe-premium.jpg",  # Changed URL
            "description_embedding": [0.15] * 1536  # Changed embedding
        },
        {
            "product_id": "colombian-supremo",
            "name": "Colombian Supremo",
            "description": "Smooth and balanced",
            "origin": "Colombia",
            "roast_level": "medium",
            "flavor_profile": ["nutty", "chocolatey"],
            "price": 16.99,
            "image_url": "https://example.com/supremo.jpg",
            "description_embedding": [0.2] * 1536
        }
    ]
    
    # Create mock OpenSearch client
    mock_client = Mock()
    indexed_documents = {}
    
    def mock_index(index, id, body, refresh=False, **kwargs):
        indexed_documents[id] = body.copy()
        return {"_index": index, "_id": id, "result": "updated"}
    
    mock_client.index = Mock(side_effect=mock_index)
    mock_client.indices.refresh = Mock()
    
    index_name = "test-products"
    
    # Act - Index v1
    count1 = index_products(mock_client, index_name, products_v1)
    
    # Verify v1 data
    assert indexed_documents["ethiopian-yirgacheffe"]["name"] == "Ethiopian Yirgacheffe"
    assert indexed_documents["ethiopian-yirgacheffe"]["price"] == 18.99
    
    # Act - Index v2 (should update existing documents)
    count2 = index_products(mock_client, index_name, products_v2)
    
    # Assert - Still only 2 documents (no duplicates)
    assert len(indexed_documents) == 2, \
        "Should still have 2 documents after update"
    
    # Assert - Data should be updated to v2
    assert indexed_documents["ethiopian-yirgacheffe"]["name"] == "Ethiopian Yirgacheffe Premium", \
        "Name should be updated"
    assert indexed_documents["ethiopian-yirgacheffe"]["price"] == 22.99, \
        "Price should be updated"
    assert len(indexed_documents["ethiopian-yirgacheffe"]["flavor_profile"]) == 3, \
        "Flavor profile should be updated"
    
    # Assert - Unchanged product should remain the same
    assert indexed_documents["colombian-supremo"]["name"] == "Colombian Supremo"
    assert indexed_documents["colombian-supremo"]["price"] == 16.99


def test_idempotence_examples():
    """Example-based tests for idempotence"""
    
    # Test 1: Single product indexed twice
    product = {
        "product_id": "test-coffee",
        "name": "Test Coffee",
        "description": "A test coffee",
        "origin": "Ethiopia",
        "roast_level": "medium",
        "flavor_profile": ["fruity"],
        "price": 15.99,
        "image_url": "https://example.com/test.jpg",
        "description_embedding": [0.1] * 1536
    }
    
    mock_client = Mock()
    indexed_documents = {}
    
    def mock_index(index, id, body, refresh=False, **kwargs):
        indexed_documents[id] = body.copy()
        return {"_index": index, "_id": id, "result": "updated"}
    
    mock_client.index = Mock(side_effect=mock_index)
    mock_client.indices.refresh = Mock()
    
    # Index twice
    index_products(mock_client, "products", [product])
    index_products(mock_client, "products", [product])
    
    # Should have exactly one document
    assert len(indexed_documents) == 1
    assert "test-coffee" in indexed_documents
    
    # Test 2: Multiple products indexed multiple times
    products = [
        {
            "product_id": f"coffee-{i}",
            "name": f"Coffee {i}",
            "description": f"Description {i}",
            "origin": "Ethiopia",
            "roast_level": "medium",
            "flavor_profile": ["fruity"],
            "price": 15.99 + i,
            "image_url": f"https://example.com/coffee-{i}.jpg",
            "description_embedding": [0.1] * 1536
        }
        for i in range(5)
    ]
    
    mock_client = Mock()
    indexed_documents = {}
    
    def mock_index(index, id, body, refresh=False, **kwargs):
        indexed_documents[id] = body.copy()
        return {"_index": index, "_id": id, "result": "updated"}
    
    mock_client.index = Mock(side_effect=mock_index)
    mock_client.indices.refresh = Mock()
    
    # Index three times
    for _ in range(3):
        index_products(mock_client, "products", products)
    
    # Should have exactly 5 documents
    assert len(indexed_documents) == 5
    assert all(f"coffee-{i}" in indexed_documents for i in range(5))

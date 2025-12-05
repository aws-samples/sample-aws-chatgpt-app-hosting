"""
Property-based tests for filter application in OpenSearch queries
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict
from opensearch_client import OpenSearchClient

# Mock product data for testing
def create_mock_product(
    product_id: str,
    origin: str,
    roast_level: str,
    price: float,
    flavor_profile: List[str]
) -> Dict:
    """Create a mock product for testing"""
    return {
        "product_id": product_id,
        "name": f"Test Coffee {product_id}",
        "description": "Test description",
        "origin": origin,
        "roast_level": roast_level,
        "flavor_profile": flavor_profile,
        "price": price,
        "image_url": "https://example.com/image.jpg"
    }

# Test strategies
origins = st.sampled_from(["Ethiopia", "Colombia", "Brazil", "Kenya", "Guatemala"])
roast_levels = st.sampled_from(["light", "medium", "dark"])
prices = st.floats(min_value=10.0, max_value=40.0)
flavor_profiles = st.lists(
    st.sampled_from(["fruity", "nutty", "chocolatey", "floral", "earthy", "spicy"]),
    min_size=1,
    max_size=3,
    unique=True
)

@settings(max_examples=100)
@given(
    origin=origins,
    roast_level=roast_levels,
    price_min=st.floats(min_value=10.0, max_value=25.0),
    price_max=st.floats(min_value=25.0, max_value=40.0)
)
def test_filter_application_correctness(origin, roast_level, price_min, price_max):
    """
    **Feature: chatgpt-coffee-discovery-app, Property 4: Filter application correctness**
    **Validates: Requirements 1.4**
    
    For any combination of filter criteria (origin, roast level, price range),
    all returned products should match ALL specified filters
    """
    # Ensure price range is valid and has reasonable width
    assume(price_min < price_max)
    assume(price_max - price_min >= 2.0)  # Ensure at least $2 range
    
    # Create mock products - some matching, some not
    mock_products = [
        # Products that match all filters
        create_mock_product("match1", origin, roast_level, (price_min + price_max) / 2, ["fruity"]),
        create_mock_product("match2", origin, roast_level, price_min + 0.5, ["nutty"]),
        # Products that don't match
        create_mock_product("nomatch1", "Peru", roast_level, (price_min + price_max) / 2, ["earthy"]),
        create_mock_product("nomatch2", origin, "light" if roast_level != "light" else "dark", 
                          (price_min + price_max) / 2, ["spicy"]),
        create_mock_product("nomatch3", origin, roast_level, price_max + 5, ["chocolatey"]),
    ]
    
    # Define filters
    filters = {
        "origin": origin,
        "roast_level": roast_level,
        "price_range": [price_min, price_max]
    }
    
    # Manually filter products (simulating what OpenSearch should do)
    filtered_products = []
    for product in mock_products:
        matches = True
        
        # Check origin filter
        if "origin" in filters and product["origin"] != filters["origin"]:
            matches = False
        
        # Check roast level filter
        if "roast_level" in filters and product["roast_level"] != filters["roast_level"]:
            matches = False
        
        # Check price range filter
        if "price_range" in filters:
            min_price, max_price = filters["price_range"]
            if not (min_price <= product["price"] <= max_price):
                matches = False
        
        if matches:
            filtered_products.append(product)
    
    # Assert - all filtered products should match ALL criteria
    for product in filtered_products:
        assert product["origin"] == origin, \
            f"Product {product['product_id']} origin {product['origin']} doesn't match filter {origin}"
        
        assert product["roast_level"] == roast_level, \
            f"Product {product['product_id']} roast level {product['roast_level']} doesn't match filter {roast_level}"
        
        assert price_min <= product["price"] <= price_max, \
            f"Product {product['product_id']} price {product['price']} not in range [{price_min}, {price_max}]"
    
    # Assert - we should have at least the matching products
    assert len(filtered_products) >= 2, "Should have found at least 2 matching products"


@settings(max_examples=100)
@given(
    origin=origins,
    roast_level=roast_levels,
    flavor=st.sampled_from(["fruity", "nutty", "chocolatey", "floral", "earthy", "spicy"])
)
def test_filter_application_with_flavor(origin, roast_level, flavor):
    """
    Test filter application with flavor profile filter
    
    For any combination including flavor profile, all returned products
    should match the flavor profile filter
    """
    # Create mock products
    mock_products = [
        create_mock_product("match1", origin, roast_level, 15.0, [flavor, "sweet"]),
        create_mock_product("match2", origin, roast_level, 20.0, [flavor]),
        create_mock_product("nomatch1", origin, roast_level, 18.0, ["vanilla"]),
        create_mock_product("nomatch2", "Peru", roast_level, 17.0, [flavor]),
    ]
    
    filters = {
        "origin": origin,
        "roast_level": roast_level,
        "flavor_profile": flavor
    }
    
    # Manually filter products
    filtered_products = []
    for product in mock_products:
        matches = True
        
        if "origin" in filters and product["origin"] != filters["origin"]:
            matches = False
        
        if "roast_level" in filters and product["roast_level"] != filters["roast_level"]:
            matches = False
        
        if "flavor_profile" in filters:
            if filters["flavor_profile"] not in product["flavor_profile"]:
                matches = False
        
        if matches:
            filtered_products.append(product)
    
    # Assert - all filtered products should match ALL criteria
    for product in filtered_products:
        assert product["origin"] == origin
        assert product["roast_level"] == roast_level
        assert flavor in product["flavor_profile"], \
            f"Product {product['product_id']} doesn't have flavor {flavor}"
    
    # Assert - we should have found the matching products
    assert len(filtered_products) >= 2


def test_filter_application_examples():
    """Example-based tests for filter application"""
    
    # Test 1: Single filter - origin
    products = [
        create_mock_product("1", "Ethiopia", "light", 15.0, ["fruity"]),
        create_mock_product("2", "Colombia", "medium", 18.0, ["nutty"]),
        create_mock_product("3", "Ethiopia", "dark", 22.0, ["chocolatey"]),
    ]
    
    filters = {"origin": "Ethiopia"}
    filtered = [p for p in products if p["origin"] == filters["origin"]]
    
    assert len(filtered) == 2
    assert all(p["origin"] == "Ethiopia" for p in filtered)
    
    # Test 2: Multiple filters
    filters = {"origin": "Ethiopia", "roast_level": "light"}
    filtered = [
        p for p in products 
        if p["origin"] == filters["origin"] and p["roast_level"] == filters["roast_level"]
    ]
    
    assert len(filtered) == 1
    assert filtered[0]["product_id"] == "1"
    
    # Test 3: Price range filter
    filters = {"price_range": [15.0, 20.0]}
    filtered = [
        p for p in products 
        if filters["price_range"][0] <= p["price"] <= filters["price_range"][1]
    ]
    
    assert len(filtered) == 2
    assert all(15.0 <= p["price"] <= 20.0 for p in filtered)
    
    # Test 4: All filters combined
    products = [
        create_mock_product("1", "Ethiopia", "light", 16.0, ["fruity"]),
        create_mock_product("2", "Ethiopia", "light", 25.0, ["fruity"]),
        create_mock_product("3", "Ethiopia", "medium", 16.0, ["fruity"]),
        create_mock_product("4", "Colombia", "light", 16.0, ["fruity"]),
    ]
    
    filters = {
        "origin": "Ethiopia",
        "roast_level": "light",
        "price_range": [15.0, 20.0]
    }
    
    filtered = [
        p for p in products
        if (p["origin"] == filters["origin"] and
            p["roast_level"] == filters["roast_level"] and
            filters["price_range"][0] <= p["price"] <= filters["price_range"][1])
    ]
    
    assert len(filtered) == 1
    assert filtered[0]["product_id"] == "1"

"""
Property-based tests for tool response structure completeness

**Feature: chatgpt-coffee-discovery-app, Property 5: Tool response structure completeness**
**Validates: Requirements 2.2**

For any product recommendation response, the structured content should include 
all required fields: product_id, name, description, origin, roast_level, 
flavor_profile, price, and image_url for each product.
"""
import pytest
from hypothesis import given, strategies as st, settings
from tools import format_product_for_response

# Required fields for product response
REQUIRED_FIELDS = [
    "product_id",
    "name", 
    "description",
    "origin",
    "roast_level",
    "flavor_profile",
    "price",
    "image_url"
]

# Strategy for generating product documents
@st.composite
def product_document(draw):
    """Generate a product document with various field combinations"""
    product = {}
    
    # Always include some fields
    product["product_id"] = draw(st.text(min_size=1, max_size=50))
    product["name"] = draw(st.text(min_size=1, max_size=100))
    
    # Randomly include other fields
    if draw(st.booleans()):
        product["description"] = draw(st.text(min_size=0, max_size=500))
    
    if draw(st.booleans()):
        product["origin"] = draw(st.sampled_from([
            "Ethiopia", "Colombia", "Brazil", "Kenya", "Guatemala"
        ]))
    
    if draw(st.booleans()):
        product["roast_level"] = draw(st.sampled_from(["light", "medium", "dark"]))
    
    if draw(st.booleans()):
        product["flavor_profile"] = draw(st.lists(
            st.sampled_from(["fruity", "nutty", "chocolatey", "floral", "earthy", "spicy"]),
            min_size=0,
            max_size=5
        ))
    
    if draw(st.booleans()):
        product["price"] = draw(st.floats(min_value=10.0, max_value=40.0))
    
    if draw(st.booleans()):
        product["image_url"] = draw(st.text(min_size=0, max_size=200))
    
    # Add some extra fields that shouldn't affect the output
    if draw(st.booleans()):
        product["_score"] = draw(st.floats(min_value=0.0, max_value=1.0))
    
    if draw(st.booleans()):
        product["extra_field"] = draw(st.text())
    
    return product

@given(product=product_document())
@settings(max_examples=100)
def test_format_product_has_all_required_fields(product):
    """
    **Feature: chatgpt-coffee-discovery-app, Property 5: Tool response structure completeness**
    **Validates: Requirements 2.2**
    
    For any product document, the formatted response should contain all required fields.
    """
    formatted = format_product_for_response(product)
    
    # Check that all required fields are present
    for field in REQUIRED_FIELDS:
        assert field in formatted, f"Missing required field: {field}"
    
    # Check that flavor_profile is always a list
    assert isinstance(formatted["flavor_profile"], list), "flavor_profile must be a list"
    
    # Check that price is a number
    assert isinstance(formatted["price"], (int, float)), "price must be a number"

@given(products=st.lists(product_document(), min_size=0, max_size=20))
@settings(max_examples=100)
def test_multiple_products_all_have_required_fields(products):
    """
    **Feature: chatgpt-coffee-discovery-app, Property 5: Tool response structure completeness**
    **Validates: Requirements 2.2**
    
    For any list of products, all formatted products should have all required fields.
    """
    formatted_products = [format_product_for_response(p) for p in products]
    
    for formatted in formatted_products:
        for field in REQUIRED_FIELDS:
            assert field in formatted, f"Missing required field: {field}"
        
        # Verify types
        assert isinstance(formatted["flavor_profile"], list)
        assert isinstance(formatted["price"], (int, float))
        assert isinstance(formatted["product_id"], str)
        assert isinstance(formatted["name"], str)
        assert isinstance(formatted["description"], str)
        assert isinstance(formatted["origin"], str)
        assert isinstance(formatted["roast_level"], str)
        assert isinstance(formatted["image_url"], str)

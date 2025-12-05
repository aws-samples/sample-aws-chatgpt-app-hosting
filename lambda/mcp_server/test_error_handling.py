"""
Property-based tests for error handling graceful degradation

**Feature: chatgpt-coffee-discovery-app, Property 9: Error handling graceful degradation**
**Validates: Requirements 4.7**

For any invalid request to the MCP Server, the system should return an error 
response with a descriptive message and not crash.
"""
import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch
from typing import Dict, Any
from tools import search_products, get_product_details, refine_preferences

# Strategy for generating invalid inputs
invalid_strings = st.one_of(
    st.none(),
    st.just(""),
    st.just("   "),
    st.text(min_size=0, max_size=0),
)

valid_strings = st.text(min_size=1, max_size=200)

# Strategy for non-empty strings (after stripping whitespace)
non_empty_strings = st.text(min_size=1, max_size=200).filter(lambda s: s.strip() != "")

# Strategy for generating various filter dictionaries (some invalid)
@st.composite
def filter_dict(draw):
    """Generate filter dictionaries with potentially invalid values"""
    filters = {}
    
    # Randomly add fields with various types
    if draw(st.booleans()):
        filters["origin"] = draw(st.one_of(
            st.text(),
            st.integers(),
            st.none(),
            st.lists(st.text())
        ))
    
    if draw(st.booleans()):
        filters["roast_level"] = draw(st.one_of(
            st.text(),
            st.integers(),
            st.none(),
            st.lists(st.text())
        ))
    
    if draw(st.booleans()):
        filters["price_range"] = draw(st.one_of(
            st.lists(st.floats(allow_nan=False, allow_infinity=False), min_size=0, max_size=5),
            st.text(),
            st.integers(),
            st.none()
        ))
    
    if draw(st.booleans()):
        filters["flavor_profile"] = draw(st.one_of(
            st.text(),
            st.lists(st.text()),
            st.integers(),
            st.none()
        ))
    
    return filters if filters else None


@settings(max_examples=100)
@given(preferences=st.one_of(invalid_strings, valid_strings))
def test_search_products_handles_invalid_preferences(preferences):
    """
    **Feature: chatgpt-coffee-discovery-app, Property 9: Error handling graceful degradation**
    **Validates: Requirements 4.7**
    
    For any preference string (including invalid ones), search_products should 
    not crash and should return a valid response structure.
    """
    # Mock the dependencies to avoid actual API calls
    with patch('tools.get_opensearch_client') as mock_os, \
         patch('tools.get_embeddings_generator') as mock_emb:
        
        # Configure mocks to return valid data
        mock_os_instance = Mock()
        mock_os_instance.semantic_search.return_value = []
        mock_os.return_value = mock_os_instance
        
        mock_emb_instance = Mock()
        mock_emb_instance.generate_embedding.return_value = [0.1] * 1536
        mock_emb.return_value = mock_emb_instance
        
        # Act - should not crash
        result = search_products(preferences, None)
        
        # Assert - result should be a dictionary
        assert isinstance(result, dict), "Result should be a dictionary"
        
        # Assert - should have required top-level keys
        assert "content" in result, "Result should have 'content' key"
        assert "structuredContent" in result, "Result should have 'structuredContent' key"
        
        # Assert - content should be a list
        assert isinstance(result["content"], list), "Content should be a list"
        
        # Assert - structuredContent should be a dictionary
        assert isinstance(result["structuredContent"], dict), "StructuredContent should be a dict"
        
        # Assert - structuredContent should have products array
        assert "products" in result["structuredContent"], "StructuredContent should have 'products'"
        assert isinstance(result["structuredContent"]["products"], list), "Products should be a list"
        
        # Assert - structuredContent should have message
        assert "message" in result["structuredContent"], "StructuredContent should have 'message'"


@settings(max_examples=100)
@given(product_id=st.one_of(invalid_strings, valid_strings))
def test_get_product_details_handles_invalid_product_id(product_id):
    """
    **Feature: chatgpt-coffee-discovery-app, Property 9: Error handling graceful degradation**
    **Validates: Requirements 4.7**
    
    For any product ID (including invalid ones), get_product_details should 
    not crash and should return a valid response structure.
    """
    # Mock the OpenSearch client
    with patch('tools.get_opensearch_client') as mock_os:
        mock_os_instance = Mock()
        mock_os_instance.get_product_by_id.return_value = None
        mock_os.return_value = mock_os_instance
        
        # Act - should not crash
        result = get_product_details(product_id)
        
        # Assert - result should be a dictionary
        assert isinstance(result, dict), "Result should be a dictionary"
        
        # Assert - should have required top-level keys
        assert "content" in result, "Result should have 'content' key"
        assert "structuredContent" in result, "Result should have 'structuredContent' key"
        
        # Assert - content should be a list
        assert isinstance(result["content"], list), "Content should be a list"
        
        # Assert - structuredContent should be a dictionary
        assert isinstance(result["structuredContent"], dict), "StructuredContent should be a dict"
        
        # Assert - structuredContent should have products array
        assert "products" in result["structuredContent"], "StructuredContent should have 'products'"
        assert isinstance(result["structuredContent"]["products"], list), "Products should be a list"


@settings(max_examples=100)
@given(
    exclude=st.one_of(
        st.none(),
        st.lists(st.text(), min_size=0, max_size=10),
        st.lists(st.integers(), min_size=0, max_size=5),
        st.text(),
        st.integers()
    ),
    similar_to=st.one_of(invalid_strings, valid_strings)
)
def test_refine_preferences_handles_invalid_inputs(exclude, similar_to):
    """
    **Feature: chatgpt-coffee-discovery-app, Property 9: Error handling graceful degradation**
    **Validates: Requirements 4.7**
    
    For any combination of exclude and similar_to parameters (including invalid ones),
    refine_preferences should not crash and should return a valid response structure.
    """
    # Mock the dependencies
    with patch('tools.get_opensearch_client') as mock_os, \
         patch('tools.get_embeddings_generator') as mock_emb:
        
        mock_os_instance = Mock()
        mock_os_instance.get_product_by_id.return_value = None
        mock_os_instance.semantic_search.return_value = []
        mock_os_instance.filtered_search.return_value = []
        mock_os.return_value = mock_os_instance
        
        mock_emb_instance = Mock()
        mock_emb_instance.generate_embedding.return_value = [0.1] * 1536
        mock_emb.return_value = mock_emb_instance
        
        # Act - should not crash
        result = refine_preferences(exclude=exclude, similar_to=similar_to, filters=None)
        
        # Assert - result should be a dictionary
        assert isinstance(result, dict), "Result should be a dictionary"
        
        # Assert - should have required top-level keys
        assert "content" in result, "Result should have 'content' key"
        assert "structuredContent" in result, "Result should have 'structuredContent' key"
        
        # Assert - content should be a list
        assert isinstance(result["content"], list), "Content should be a list"
        
        # Assert - structuredContent should be a dictionary
        assert isinstance(result["structuredContent"], dict), "StructuredContent should be a dict"
        
        # Assert - structuredContent should have products array
        assert "products" in result["structuredContent"], "StructuredContent should have 'products'"
        assert isinstance(result["structuredContent"]["products"], list), "Products should be a list"


@settings(max_examples=100)
@given(preferences=non_empty_strings)
def test_search_products_handles_opensearch_errors(preferences):
    """
    **Feature: chatgpt-coffee-discovery-app, Property 9: Error handling graceful degradation**
    **Validates: Requirements 4.7**
    
    When OpenSearch raises an exception, search_products should handle it gracefully
    and return an error response without crashing.
    """
    # Mock OpenSearch to raise an exception
    with patch('tools.get_opensearch_client') as mock_os, \
         patch('tools.get_embeddings_generator') as mock_emb:
        
        mock_os_instance = Mock()
        mock_os_instance.semantic_search.side_effect = Exception("OpenSearch connection failed")
        mock_os.return_value = mock_os_instance
        
        mock_emb_instance = Mock()
        mock_emb_instance.generate_embedding.return_value = [0.1] * 1536
        mock_emb.return_value = mock_emb_instance
        
        # Act - should not crash
        result = search_products(preferences, None)
        
        # Assert - result should be a dictionary
        assert isinstance(result, dict), "Result should be a dictionary"
        
        # Assert - should have error indicator in structuredContent
        assert "structuredContent" in result
        assert "error" in result["structuredContent"], "Should indicate error occurred"
        assert result["structuredContent"]["error"] is True, "Error flag should be True"
        
        # Assert - should have error message
        assert "message" in result["structuredContent"]
        assert len(result["structuredContent"]["message"]) > 0, "Should have error message"
        
        # Assert - should have empty products array
        assert "products" in result["structuredContent"]
        assert result["structuredContent"]["products"] == [], "Products should be empty on error"


@settings(max_examples=100)
@given(preferences=non_empty_strings)
def test_search_products_handles_embeddings_errors(preferences):
    """
    **Feature: chatgpt-coffee-discovery-app, Property 9: Error handling graceful degradation**
    **Validates: Requirements 4.7**
    
    When embeddings generation raises an exception, search_products should handle 
    it gracefully and return an error response without crashing.
    """
    # Mock embeddings generator to raise an exception
    with patch('tools.get_opensearch_client') as mock_os, \
         patch('tools.get_embeddings_generator') as mock_emb:
        
        mock_os_instance = Mock()
        mock_os.return_value = mock_os_instance
        
        mock_emb_instance = Mock()
        mock_emb_instance.generate_embedding.side_effect = Exception("Bedrock API error")
        mock_emb.return_value = mock_emb_instance
        
        # Act - should not crash
        result = search_products(preferences, None)
        
        # Assert - result should be a dictionary
        assert isinstance(result, dict), "Result should be a dictionary"
        
        # Assert - should have error indicator
        assert "structuredContent" in result
        assert "error" in result["structuredContent"], "Should indicate error occurred"
        assert result["structuredContent"]["error"] is True, "Error flag should be True"
        
        # Assert - should have error message
        assert "message" in result["structuredContent"]
        assert len(result["structuredContent"]["message"]) > 0, "Should have error message"


@settings(max_examples=100)
@given(product_id=non_empty_strings)
def test_get_product_details_handles_opensearch_errors(product_id):
    """
    **Feature: chatgpt-coffee-discovery-app, Property 9: Error handling graceful degradation**
    **Validates: Requirements 4.7**
    
    When OpenSearch raises an exception, get_product_details should handle it 
    gracefully and return an error response without crashing.
    """
    # Mock OpenSearch to raise an exception
    with patch('tools.get_opensearch_client') as mock_os:
        mock_os_instance = Mock()
        mock_os_instance.get_product_by_id.side_effect = Exception("OpenSearch query failed")
        mock_os.return_value = mock_os_instance
        
        # Act - should not crash
        result = get_product_details(product_id)
        
        # Assert - result should be a dictionary
        assert isinstance(result, dict), "Result should be a dictionary"
        
        # Assert - should have error indicator
        assert "structuredContent" in result
        assert "error" in result["structuredContent"], "Should indicate error occurred"
        assert result["structuredContent"]["error"] is True, "Error flag should be True"
        
        # Assert - should have error message
        assert "message" in result["structuredContent"]
        assert len(result["structuredContent"]["message"]) > 0, "Should have error message"


def test_error_response_structure_is_consistent():
    """
    **Feature: chatgpt-coffee-discovery-app, Property 9: Error handling graceful degradation**
    **Validates: Requirements 4.7**
    
    All error responses should have a consistent structure with error flag,
    message, and empty products array.
    """
    # Test search_products error
    with patch('tools.get_opensearch_client') as mock_os, \
         patch('tools.get_embeddings_generator') as mock_emb:
        
        mock_os_instance = Mock()
        mock_os_instance.semantic_search.side_effect = Exception("Test error")
        mock_os.return_value = mock_os_instance
        
        mock_emb_instance = Mock()
        mock_emb_instance.generate_embedding.return_value = [0.1] * 1536
        mock_emb.return_value = mock_emb_instance
        
        result1 = search_products("test", None)
        
        # Verify structure
        assert result1["structuredContent"]["error"] is True
        assert isinstance(result1["structuredContent"]["message"], str)
        assert result1["structuredContent"]["products"] == []
    
    # Test get_product_details error
    with patch('tools.get_opensearch_client') as mock_os:
        mock_os_instance = Mock()
        mock_os_instance.get_product_by_id.side_effect = Exception("Test error")
        mock_os.return_value = mock_os_instance
        
        result2 = get_product_details("test-id")
        
        # Verify structure
        assert result2["structuredContent"]["error"] is True
        assert isinstance(result2["structuredContent"]["message"], str)
        assert result2["structuredContent"]["products"] == []
    
    # Test refine_preferences error
    with patch('tools.get_opensearch_client') as mock_os, \
         patch('tools.get_embeddings_generator') as mock_emb:
        
        mock_os_instance = Mock()
        mock_os_instance.filtered_search.side_effect = Exception("Test error")
        mock_os.return_value = mock_os_instance
        
        mock_emb_instance = Mock()
        mock_emb.return_value = mock_emb_instance
        
        result3 = refine_preferences(exclude=["dark"], similar_to=None, filters={"origin": "Ethiopia"})
        
        # Verify structure
        assert result3["structuredContent"]["error"] is True
        assert isinstance(result3["structuredContent"]["message"], str)
        assert result3["structuredContent"]["products"] == []


def test_empty_and_whitespace_inputs_handled_gracefully():
    """
    **Feature: chatgpt-coffee-discovery-app, Property 9: Error handling graceful degradation**
    **Validates: Requirements 4.7**
    
    Empty and whitespace-only inputs should be handled gracefully without errors.
    """
    # Test empty preference
    result = search_products("", None)
    assert isinstance(result, dict)
    assert "structuredContent" in result
    assert "products" in result["structuredContent"]
    
    # Test whitespace-only preference
    result = search_products("   ", None)
    assert isinstance(result, dict)
    assert "structuredContent" in result
    assert "products" in result["structuredContent"]
    
    # Test empty product ID
    with patch('tools.get_opensearch_client') as mock_os:
        mock_os_instance = Mock()
        mock_os.return_value = mock_os_instance
        
        result = get_product_details("")
        assert isinstance(result, dict)
        assert "structuredContent" in result
        assert "products" in result["structuredContent"]
    
    # Test whitespace-only product ID
    with patch('tools.get_opensearch_client') as mock_os:
        mock_os_instance = Mock()
        mock_os.return_value = mock_os_instance
        
        result = get_product_details("   ")
        assert isinstance(result, dict)
        assert "structuredContent" in result
        assert "products" in result["structuredContent"]

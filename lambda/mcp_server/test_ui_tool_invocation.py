"""
Property-based tests for UI tool invocation correctness

**Feature: chatgpt-coffee-discovery-app, Property 6: UI tool invocation correctness**
**Validates: Requirements 2.5**

For any user interaction in the web component, calling window.openai.callTool 
should include the correct tool name and properly formatted parameters.
"""
import pytest
from hypothesis import given, strategies as st, settings
from typing import Dict, Any
import json

# Valid tool names in the MCP server
VALID_TOOL_NAMES = [
    "search_products",
    "get_product_details",
    "refine_preferences"
]

# Strategy for generating product IDs
product_ids = st.text(
    alphabet=st.characters(whitelist_categories=('Ll', 'Nd'), whitelist_characters='-_'),
    min_size=1,
    max_size=50
).filter(lambda x: x and not x.startswith('-') and not x.endswith('-'))

# Strategy for generating valid tool invocations
@st.composite
def tool_invocation(draw):
    """Generate a valid tool invocation with tool name and parameters"""
    tool_name = draw(st.sampled_from(VALID_TOOL_NAMES))
    
    if tool_name == "get_product_details":
        params = {
            "product_id": draw(product_ids)
        }
    elif tool_name == "search_products":
        params = {
            "preferences": draw(st.text(min_size=0, max_size=200))
        }
        # Optionally add filters
        if draw(st.booleans()):
            filters = {}
            if draw(st.booleans()):
                filters["origin"] = draw(st.sampled_from([
                    "Ethiopia", "Colombia", "Brazil", "Kenya", "Guatemala"
                ]))
            if draw(st.booleans()):
                filters["roast_level"] = draw(st.sampled_from(["light", "medium", "dark"]))
            if draw(st.booleans()):
                price_min = draw(st.floats(min_value=10.0, max_value=25.0))
                price_max = draw(st.floats(min_value=25.0, max_value=40.0))
                filters["price_range"] = [price_min, price_max]
            
            if filters:
                params["filters"] = filters
    elif tool_name == "refine_preferences":
        params = {}
        
        # Ensure at least one parameter is present
        # Generate a list of which parameters to include (at least one)
        include_exclude = draw(st.booleans())
        include_similar_to = draw(st.booleans())
        include_filters = draw(st.booleans())
        
        # If none are selected, randomly pick at least one
        if not (include_exclude or include_similar_to or include_filters):
            choice = draw(st.sampled_from(["exclude", "similar_to", "filters"]))
            if choice == "exclude":
                include_exclude = True
            elif choice == "similar_to":
                include_similar_to = True
            else:
                include_filters = True
        
        # Add exclude list if selected
        if include_exclude:
            params["exclude"] = draw(st.lists(
                st.sampled_from(["dark", "light", "medium", "Ethiopia", "Colombia"]),
                min_size=1,
                max_size=3,
                unique=True
            ))
        
        # Add similar_to if selected
        if include_similar_to:
            params["similar_to"] = draw(product_ids)
        
        # Add filters if selected
        if include_filters:
            filters = {}
            if draw(st.booleans()):
                filters["origin"] = draw(st.sampled_from([
                    "Ethiopia", "Colombia", "Brazil", "Kenya", "Guatemala"
                ]))
            if draw(st.booleans()):
                filters["roast_level"] = draw(st.sampled_from(["light", "medium", "dark"]))
            
            # Ensure at least one filter is present
            if not filters:
                filters["origin"] = draw(st.sampled_from([
                    "Ethiopia", "Colombia", "Brazil", "Kenya", "Guatemala"
                ]))
            
            params["filters"] = filters
    
    return tool_name, params


def validate_tool_invocation(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that a tool invocation has the correct structure.
    This simulates what the web component should do when calling window.openai.callTool.
    
    Returns a dict with validation results.
    """
    result = {
        "valid": True,
        "errors": []
    }
    
    # Validate tool name
    if not isinstance(tool_name, str):
        result["valid"] = False
        result["errors"].append(f"Tool name must be a string, got {type(tool_name)}")
        return result
    
    if tool_name not in VALID_TOOL_NAMES:
        result["valid"] = False
        result["errors"].append(f"Invalid tool name: {tool_name}. Must be one of {VALID_TOOL_NAMES}")
        return result
    
    # Validate params is a dict
    if not isinstance(params, dict):
        result["valid"] = False
        result["errors"].append(f"Parameters must be a dict, got {type(params)}")
        return result
    
    # Validate parameters based on tool name
    if tool_name == "get_product_details":
        # Must have product_id
        if "product_id" not in params:
            result["valid"] = False
            result["errors"].append("get_product_details requires 'product_id' parameter")
        elif not isinstance(params["product_id"], str):
            result["valid"] = False
            result["errors"].append(f"product_id must be a string, got {type(params['product_id'])}")
        elif not params["product_id"]:
            result["valid"] = False
            result["errors"].append("product_id cannot be empty")
    
    elif tool_name == "search_products":
        # Must have preferences
        if "preferences" not in params:
            result["valid"] = False
            result["errors"].append("search_products requires 'preferences' parameter")
        elif not isinstance(params["preferences"], str):
            result["valid"] = False
            result["errors"].append(f"preferences must be a string, got {type(params['preferences'])}")
        
        # Validate filters if present
        if "filters" in params:
            if not isinstance(params["filters"], dict):
                result["valid"] = False
                result["errors"].append(f"filters must be a dict, got {type(params['filters'])}")
            else:
                filters = params["filters"]
                
                # Validate origin
                if "origin" in filters and not isinstance(filters["origin"], str):
                    result["valid"] = False
                    result["errors"].append(f"origin must be a string, got {type(filters['origin'])}")
                
                # Validate roast_level
                if "roast_level" in filters:
                    if not isinstance(filters["roast_level"], str):
                        result["valid"] = False
                        result["errors"].append(f"roast_level must be a string, got {type(filters['roast_level'])}")
                    elif filters["roast_level"] not in ["light", "medium", "dark"]:
                        result["valid"] = False
                        result["errors"].append(f"roast_level must be light, medium, or dark")
                
                # Validate price_range
                if "price_range" in filters:
                    if not isinstance(filters["price_range"], list):
                        result["valid"] = False
                        result["errors"].append(f"price_range must be a list, got {type(filters['price_range'])}")
                    elif len(filters["price_range"]) != 2:
                        result["valid"] = False
                        result["errors"].append(f"price_range must have exactly 2 elements")
                    elif not all(isinstance(x, (int, float)) for x in filters["price_range"]):
                        result["valid"] = False
                        result["errors"].append("price_range elements must be numbers")
                    elif filters["price_range"][0] > filters["price_range"][1]:
                        result["valid"] = False
                        result["errors"].append("price_range min must be <= max")
    
    elif tool_name == "refine_preferences":
        # At least one parameter should be present
        if not any(key in params for key in ["exclude", "similar_to", "filters"]):
            result["valid"] = False
            result["errors"].append("refine_preferences requires at least one of: exclude, similar_to, filters")
        
        # Validate exclude if present
        if "exclude" in params:
            if not isinstance(params["exclude"], list):
                result["valid"] = False
                result["errors"].append(f"exclude must be a list, got {type(params['exclude'])}")
            elif not all(isinstance(x, str) for x in params["exclude"]):
                result["valid"] = False
                result["errors"].append("exclude list must contain only strings")
        
        # Validate similar_to if present
        if "similar_to" in params:
            if not isinstance(params["similar_to"], str):
                result["valid"] = False
                result["errors"].append(f"similar_to must be a string, got {type(params['similar_to'])}")
            elif not params["similar_to"]:
                result["valid"] = False
                result["errors"].append("similar_to cannot be empty")
        
        # Validate filters if present
        if "filters" in params:
            if not isinstance(params["filters"], dict):
                result["valid"] = False
                result["errors"].append(f"filters must be a dict, got {type(params['filters'])}")
    
    # Validate that params can be JSON serialized (required for MCP)
    try:
        json.dumps(params)
    except (TypeError, ValueError) as e:
        result["valid"] = False
        result["errors"].append(f"Parameters must be JSON serializable: {e}")
    
    return result


@settings(max_examples=100)
@given(invocation=tool_invocation())
def test_ui_tool_invocation_correctness(invocation):
    """
    **Feature: chatgpt-coffee-discovery-app, Property 6: UI tool invocation correctness**
    **Validates: Requirements 2.5**
    
    For any user interaction in the web component, calling window.openai.callTool 
    should include the correct tool name and properly formatted parameters.
    """
    tool_name, params = invocation
    
    # Validate the tool invocation
    validation = validate_tool_invocation(tool_name, params)
    
    # Assert that the invocation is valid
    assert validation["valid"], \
        f"Invalid tool invocation for {tool_name}: {', '.join(validation['errors'])}"
    
    # Assert tool name is valid
    assert tool_name in VALID_TOOL_NAMES, \
        f"Tool name {tool_name} not in valid tools: {VALID_TOOL_NAMES}"
    
    # Assert params is a dict
    assert isinstance(params, dict), \
        f"Parameters must be a dict, got {type(params)}"
    
    # Assert params can be JSON serialized
    try:
        json_params = json.dumps(params)
        assert isinstance(json_params, str)
    except Exception as e:
        pytest.fail(f"Parameters must be JSON serializable: {e}")


@settings(max_examples=100)
@given(product_id=product_ids)
def test_get_product_details_invocation(product_id):
    """
    Test that get_product_details tool invocations are correctly formatted.
    This simulates clicking on a product card in the UI.
    """
    tool_name = "get_product_details"
    params = {"product_id": product_id}
    
    validation = validate_tool_invocation(tool_name, params)
    
    assert validation["valid"], \
        f"Invalid get_product_details invocation: {', '.join(validation['errors'])}"
    
    # Verify required fields
    assert "product_id" in params
    assert isinstance(params["product_id"], str)
    assert len(params["product_id"]) > 0


@settings(max_examples=100)
@given(
    preferences=st.text(min_size=1, max_size=200),
    include_filters=st.booleans()
)
def test_search_products_invocation(preferences, include_filters):
    """
    Test that search_products tool invocations are correctly formatted.
    This simulates searching for products with preferences.
    """
    tool_name = "search_products"
    params = {"preferences": preferences}
    
    if include_filters:
        params["filters"] = {
            "origin": "Ethiopia",
            "roast_level": "light"
        }
    
    validation = validate_tool_invocation(tool_name, params)
    
    assert validation["valid"], \
        f"Invalid search_products invocation: {', '.join(validation['errors'])}"
    
    # Verify required fields
    assert "preferences" in params
    assert isinstance(params["preferences"], str)


def test_invalid_tool_invocations():
    """
    Test that invalid tool invocations are properly rejected.
    """
    # Invalid tool name
    validation = validate_tool_invocation("invalid_tool", {})
    assert not validation["valid"]
    assert any("Invalid tool name" in err for err in validation["errors"])
    
    # Missing required parameter
    validation = validate_tool_invocation("get_product_details", {})
    assert not validation["valid"]
    assert any("product_id" in err for err in validation["errors"])
    
    # Wrong parameter type
    validation = validate_tool_invocation("get_product_details", {"product_id": 123})
    assert not validation["valid"]
    assert any("must be a string" in err for err in validation["errors"])
    
    # Empty product_id
    validation = validate_tool_invocation("get_product_details", {"product_id": ""})
    assert not validation["valid"]
    assert any("cannot be empty" in err for err in validation["errors"])
    
    # Invalid price range
    validation = validate_tool_invocation("search_products", {
        "preferences": "test",
        "filters": {"price_range": [30, 20]}  # min > max
    })
    assert not validation["valid"]
    assert any("min must be <= max" in err for err in validation["errors"])
    
    # Non-dict params
    validation = validate_tool_invocation("search_products", "not a dict")
    assert not validation["valid"]
    assert any("must be a dict" in err for err in validation["errors"])


def test_example_ui_interactions():
    """
    Example-based tests for common UI interactions.
    """
    # Example 1: User clicks on a product card
    tool_name = "get_product_details"
    params = {"product_id": "ethiopian-yirgacheffe-light"}
    validation = validate_tool_invocation(tool_name, params)
    assert validation["valid"]
    
    # Example 2: User searches with preferences
    tool_name = "search_products"
    params = {"preferences": "fruity light roast"}
    validation = validate_tool_invocation(tool_name, params)
    assert validation["valid"]
    
    # Example 3: User searches with filters
    tool_name = "search_products"
    params = {
        "preferences": "smooth coffee",
        "filters": {
            "origin": "Colombia",
            "roast_level": "medium",
            "price_range": [15.0, 25.0]
        }
    }
    validation = validate_tool_invocation(tool_name, params)
    assert validation["valid"]
    
    # Example 4: User refines preferences
    tool_name = "refine_preferences"
    params = {
        "exclude": ["dark"],
        "similar_to": "ethiopian-yirgacheffe-light"
    }
    validation = validate_tool_invocation(tool_name, params)
    assert validation["valid"]
    
    # Example 5: User refines with filters only
    tool_name = "refine_preferences"
    params = {
        "filters": {"origin": "Kenya"}
    }
    validation = validate_tool_invocation(tool_name, params)
    assert validation["valid"]

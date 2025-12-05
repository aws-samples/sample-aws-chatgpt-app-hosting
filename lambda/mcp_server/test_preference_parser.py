"""
Property-based tests for preference parser
"""
import pytest
from hypothesis import given, strategies as st, settings
from preference_parser import parse_preferences

# Test strategies
preference_strings = st.one_of(
    st.text(min_size=0, max_size=200),  # Random text
    st.just(""),  # Empty string
    st.just("   "),  # Whitespace only
    st.builds(
        lambda *parts: " ".join(parts),
        st.sampled_from(["light", "medium", "dark", ""]),
        st.sampled_from(["roast", ""]),
        st.sampled_from(["from", ""]),
        st.sampled_from(["Ethiopia", "Colombia", "Brazil", "Kenya", ""]),
        st.sampled_from(["fruity", "nutty", "chocolatey", ""]),
    ),
)

@settings(max_examples=100)
@given(preferences=preference_strings)
def test_preference_parsing_robustness(preferences):
    """
    **Feature: chatgpt-coffee-discovery-app, Property 1: Preference parsing robustness**
    **Validates: Requirements 1.1**
    
    For any user preference string, the MCP Server should parse it without crashing
    and extract valid attributes (or return empty attributes for unparseable input)
    """
    # Act - should not crash
    result = parse_preferences(preferences)
    
    # Assert - result should be a dictionary
    assert isinstance(result, dict), "Parser should always return a dictionary"
    
    # Assert - all keys should be valid attribute names
    valid_keys = {"origin", "roast_level", "flavor_profile", "price_range"}
    for key in result.keys():
        assert key in valid_keys, f"Invalid attribute key: {key}"
    
    # Assert - origin should be a valid country name if present
    if "origin" in result:
        valid_origins = [
            "Ethiopia", "Colombia", "Brazil", "Kenya", "Guatemala",
            "Costa Rica", "Sumatra", "Yemen", "Peru"
        ]
        assert result["origin"] in valid_origins, f"Invalid origin: {result['origin']}"
    
    # Assert - roast_level should be valid if present
    if "roast_level" in result:
        valid_roasts = ["light", "medium", "dark"]
        assert result["roast_level"] in valid_roasts, f"Invalid roast level: {result['roast_level']}"
    
    # Assert - flavor_profile should be a list if present
    if "flavor_profile" in result:
        assert isinstance(result["flavor_profile"], list), "Flavor profile should be a list"
        assert len(result["flavor_profile"]) > 0, "Flavor profile list should not be empty"
    
    # Assert - price_range should be a valid range if present
    if "price_range" in result:
        assert isinstance(result["price_range"], list), "Price range should be a list"
        assert len(result["price_range"]) == 2, "Price range should have exactly 2 elements"
        assert result["price_range"][0] <= result["price_range"][1], "Price range should be [min, max]"
        assert result["price_range"][0] >= 0, "Minimum price should be non-negative"


def test_preference_parsing_examples():
    """Example-based tests for common preference patterns"""
    
    # Test 1: Simple preference
    result = parse_preferences("light roast from Ethiopia")
    assert result.get("roast_level") == "light"
    assert result.get("origin") == "Ethiopia"
    
    # Test 2: With flavor
    result = parse_preferences("fruity medium roast")
    assert result.get("roast_level") == "medium"
    assert "fruity" in result.get("flavor_profile", [])
    
    # Test 3: Empty string
    result = parse_preferences("")
    assert result == {}
    
    # Test 4: Whitespace only
    result = parse_preferences("   ")
    assert result == {}
    
    # Test 5: Budget preference
    result = parse_preferences("budget coffee")
    assert "price_range" in result
    assert result["price_range"][0] == 12
    assert result["price_range"][1] == 15

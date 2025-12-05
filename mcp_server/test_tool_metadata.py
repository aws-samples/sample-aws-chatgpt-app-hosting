"""
Property-based tests for tool metadata completeness

**Feature: chatgpt-coffee-discovery-app, Property 8: Tool metadata completeness**
**Validates: Requirements 4.6**

For any registered MCP tool, it should include the "openai/outputTemplate" 
metadata field linking to the web component resource.
"""
import pytest
import inspect
import asyncio
from hypothesis import given, strategies as st, settings
from server import mcp

# Expected output template
EXPECTED_OUTPUT_TEMPLATE = "ui://widget/coffee-discovery.html"

# Tool names we expect to be registered
EXPECTED_TOOLS = [
    "search_products_tool",
    "get_product_details_tool", 
    "refine_preferences_tool"
]

def test_all_expected_tools_are_registered():
    """
    **Feature: chatgpt-coffee-discovery-app, Property 8: Tool metadata completeness**
    **Validates: Requirements 4.6**
    
    All expected tools should be registered with the MCP server.
    """
    # Get registered tools from FastMCP tool manager
    tools_dict = asyncio.run(mcp._tool_manager.get_tools())
    registered_tools = list(tools_dict.keys())
    
    # Verify we found the tools
    assert len(registered_tools) > 0, "Could not find any registered tools in MCP server"
    
    for tool_name in EXPECTED_TOOLS:
        assert tool_name in registered_tools, f"Tool {tool_name} is not registered. Found: {registered_tools}"

def test_all_tools_have_output_template_metadata():
    """
    **Feature: chatgpt-coffee-discovery-app, Property 8: Tool metadata completeness**
    **Validates: Requirements 4.6**
    
    For any registered tool, it should have the openai/outputTemplate metadata.
    """
    # Get registered tools from FastMCP tool manager
    tools_dict = asyncio.run(mcp._tool_manager.get_tools())
    
    for tool_name, tool_info in tools_dict.items():
        # Get annotations from the tool
        if not hasattr(tool_info, 'annotations'):
            pytest.fail(f"Tool {tool_name} does not have annotations attribute")
        
        annotations = tool_info.annotations
        
        # Check that openai/outputTemplate is present
        assert hasattr(annotations, 'openai/outputTemplate'), \
            f"Tool {tool_name} missing 'openai/outputTemplate' in annotations"
        
        output_template = getattr(annotations, 'openai/outputTemplate')
        
        # Check that it points to the correct resource
        assert output_template == EXPECTED_OUTPUT_TEMPLATE, \
            f"Tool {tool_name} has incorrect outputTemplate: {output_template}"

@given(tool_name=st.sampled_from(EXPECTED_TOOLS))
@settings(max_examples=100)
def test_each_tool_has_correct_metadata(tool_name):
    """
    **Feature: chatgpt-coffee-discovery-app, Property 8: Tool metadata completeness**
    **Validates: Requirements 4.6**
    
    For any tool in our expected list, it should have the correct metadata.
    """
    # Get registered tools from FastMCP tool manager
    tools_dict = asyncio.run(mcp._tool_manager.get_tools())
    
    # Tool should be registered
    assert tool_name in tools_dict, f"Tool {tool_name} not found in registered tools"
    
    tool_info = tools_dict[tool_name]
    
    # Get annotations from the tool
    assert hasattr(tool_info, 'annotations'), f"Tool {tool_name} does not have annotations"
    
    annotations = tool_info.annotations
    
    # Verify annotations has openai/outputTemplate
    assert hasattr(annotations, 'openai/outputTemplate'), \
        f"Tool {tool_name} missing 'openai/outputTemplate' in annotations"
    
    output_template = getattr(annotations, 'openai/outputTemplate')
    assert output_template == EXPECTED_OUTPUT_TEMPLATE, \
        f"Tool {tool_name} has incorrect outputTemplate: {output_template}"

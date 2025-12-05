"""
Lambda handler for MCP server
Adapts the FastMCP server to work with API Gateway + Lambda
"""
import json
import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add mcp_server to path
mcp_server_path = Path(__file__).parent / 'mcp_server'
if str(mcp_server_path) not in sys.path:
    sys.path.insert(0, str(mcp_server_path))

# Import the FastMCP server instance
try:
    from mcp_server.server import mcp
    logger.info("Successfully imported FastMCP server")
except ImportError as e:
    logger.error(f"Failed to import FastMCP server: {e}")
    raise


def lambda_handler(event, context):
    """
    Lambda handler that processes API Gateway requests and routes them to the MCP server.
    
    FastMCP supports stateless HTTP mode which is perfect for Lambda.
    The server handles JSON-RPC 2.0 requests at the /mcp endpoint.
    """
    
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Extract request details from API Gateway event
    http_method = event.get('httpMethod', 'POST')
    path = event.get('path', '/')
    headers = event.get('headers', {})
    body = event.get('body', '')
    
    # Parse body if it's a string
    if isinstance(body, str) and body:
        try:
            body_json = json.loads(body)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in request body")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Invalid JSON in request body'})
            }
    else:
        body_json = body
    
    # MCP protocol expects POST requests
    if http_method != 'POST':
        return {
            'statusCode': 405,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Method not allowed. Use POST.'})
        }
    
    # Process MCP request using FastMCP's stateless HTTP handler
    try:
        # FastMCP in stateless mode can handle JSON-RPC requests directly
        # The mcp instance has methods to handle the protocol
        
        # For now, we'll manually route to the appropriate handler
        # In production, FastMCP should expose a method to handle raw requests
        
        jsonrpc_method = body_json.get('method')
        jsonrpc_id = body_json.get('id')
        
        logger.info(f"Processing JSON-RPC method: {jsonrpc_method}")
        
        # Handle initialize request
        if jsonrpc_method == 'initialize':
            response_data = {
                'jsonrpc': '2.0',
                'result': {
                    'protocolVersion': '2024-11-05',
                    'capabilities': {
                        'tools': {},
                        'resources': {}
                    },
                    'serverInfo': {
                        'name': 'Coffee Discovery',
                        'version': '1.0.0'
                    }
                },
                'id': jsonrpc_id
            }
        
        # Handle tools/list request
        elif jsonrpc_method == 'tools/list':
            response_data = {
                'jsonrpc': '2.0',
                'result': {
                    'tools': [
                        {
                            'name': 'search_products_tool',
                            'title': 'Search Coffee Products',
                            'description': 'Search for coffee products based on natural language preferences.',
                            'inputSchema': {
                                'type': 'object',
                                'properties': {
                                    'preferences': {
                                        'type': 'string',
                                        'description': 'Natural language description of coffee preferences'
                                    },
                                    'filters': {
                                        'type': 'object',
                                        'description': 'Optional filters'
                                    }
                                },
                                'required': ['preferences']
                            },
                            '_meta': {
                                'openai/outputTemplate': 'ui://widget/coffee-discovery.html',
                                'openai/toolInvocation/invoking': 'Brewing your perfect coffee search...',
                                'openai/toolInvocation/invoked': 'Found your perfect beans!',
                                'openai/widgetAccessible': True,
                                'openai/resultCanProduceWidget': True
                            },
                            'annotations': {
                                'destructiveHint': False,
                                'openWorldHint': False,
                                'readOnlyHint': True
                            }
                        },
                        {
                            'name': 'get_product_details_tool',
                            'title': 'Get Coffee Product Details',
                            'description': 'Get detailed information about a specific coffee product.',
                            'inputSchema': {
                                'type': 'object',
                                'properties': {
                                    'product_id': {
                                        'type': 'string',
                                        'description': 'Unique product identifier'
                                    }
                                },
                                'required': ['product_id']
                            },
                            '_meta': {
                                'openai/outputTemplate': 'ui://widget/coffee-discovery.html',
                                'openai/toolInvocation/invoking': 'Fetching coffee details...',
                                'openai/toolInvocation/invoked': 'Here are the details!',
                                'openai/widgetAccessible': True,
                                'openai/resultCanProduceWidget': True
                            },
                            'annotations': {
                                'destructiveHint': False,
                                'openWorldHint': False,
                                'readOnlyHint': True
                            }
                        },
                        {
                            'name': 'refine_preferences_tool',
                            'title': 'Refine Coffee Search',
                            'description': 'Refine product search with exclusions and similarity matching.',
                            'inputSchema': {
                                'type': 'object',
                                'properties': {
                                    'exclude': {
                                        'type': 'array',
                                        'items': {'type': 'string'},
                                        'description': 'List of attributes to exclude'
                                    },
                                    'similar_to': {
                                        'type': 'string',
                                        'description': 'Product ID to find similar products'
                                    },
                                    'filters': {
                                        'type': 'object',
                                        'description': 'Optional filters'
                                    }
                                }
                            },
                            '_meta': {
                                'openai/outputTemplate': 'ui://widget/coffee-discovery.html',
                                'openai/toolInvocation/invoking': 'Refining your search...',
                                'openai/toolInvocation/invoked': 'Refined results ready!',
                                'openai/widgetAccessible': True,
                                'openai/resultCanProduceWidget': True
                            },
                            'annotations': {
                                'destructiveHint': False,
                                'openWorldHint': False,
                                'readOnlyHint': True
                            }
                        }
                    ]
                },
                'id': jsonrpc_id
            }
        
        # Handle tools/call request
        elif jsonrpc_method == 'tools/call':
            tool_name = body_json.get('params', {}).get('name')
            tool_arguments = body_json.get('params', {}).get('arguments', {})
            
            logger.info(f"Calling tool: {tool_name} with arguments: {tool_arguments}")
            
            # Import and call the actual tool functions
            from mcp_server.tools import search_products, get_product_details, refine_preferences
            
            if tool_name == 'search_products_tool':
                result = search_products(
                    tool_arguments.get('preferences'),
                    tool_arguments.get('filters')
                )
            elif tool_name == 'get_product_details_tool':
                result = get_product_details(tool_arguments.get('product_id'))
            elif tool_name == 'refine_preferences_tool':
                result = refine_preferences(
                    tool_arguments.get('exclude'),
                    tool_arguments.get('similar_to'),
                    tool_arguments.get('filters')
                )
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
            
            # Build the response with BOTH content and structuredContent
            # The working example shows we need both!
            content = []
            
            # Add text content
            if 'content' in result and isinstance(result['content'], list):
                content.extend(result['content'])
            
            response_result = {
                'content': content
            }
            
            # Add structuredContent if present (widget reads from window.openai.toolOutput)
            if 'structuredContent' in result:
                response_result['structuredContent'] = result['structuredContent']
            
            # Add _meta with tool invocation status
            tool_meta = {
                'openai/toolInvocation/invoking': 'Processing...',
                'openai/toolInvocation/invoked': 'Complete!'
            }
            
            # Customize meta based on tool
            if tool_name == 'search_products_tool':
                tool_meta = {
                    'openai/toolInvocation/invoking': 'Brewing your perfect coffee search...',
                    'openai/toolInvocation/invoked': 'Found your perfect beans!'
                }
            elif tool_name == 'get_product_details_tool':
                tool_meta = {
                    'openai/toolInvocation/invoking': 'Fetching coffee details...',
                    'openai/toolInvocation/invoked': 'Here are the details!'
                }
            elif tool_name == 'refine_preferences_tool':
                tool_meta = {
                    'openai/toolInvocation/invoking': 'Refining your search...',
                    'openai/toolInvocation/invoked': 'Refined results ready!'
                }
            
            response_result['_meta'] = tool_meta
            
            response_data = {
                'jsonrpc': '2.0',
                'result': response_result,
                'id': jsonrpc_id
            }
        
        # Handle resources/list request
        elif jsonrpc_method == 'resources/list':
            widget_meta = {
                'openai/outputTemplate': 'ui://widget/coffee-discovery.html',
                'openai/widgetAccessible': True,
                'openai/resultCanProduceWidget': True
            }
            
            response_data = {
                'jsonrpc': '2.0',
                'result': {
                    'resources': [
                        {
                            'uri': 'ui://widget/coffee-discovery.html',
                            'name': 'Coffee Discovery Widget',
                            'title': 'Coffee Discovery Widget',
                            'description': 'Interactive web component for displaying coffee products',
                            'mimeType': 'text/html+skybridge',
                            '_meta': widget_meta
                        }
                    ]
                },
                'id': jsonrpc_id
            }
        
        # Handle resources/templates/list request (required by working example)
        elif jsonrpc_method == 'resources/templates/list':
            widget_meta = {
                'openai/outputTemplate': 'ui://widget/coffee-discovery.html',
                'openai/widgetAccessible': True,
                'openai/resultCanProduceWidget': True
            }
            
            response_data = {
                'jsonrpc': '2.0',
                'result': {
                    'resourceTemplates': [
                        {
                            'uriTemplate': 'ui://widget/coffee-discovery.html',
                            'name': 'Coffee Discovery Widget',
                            'title': 'Coffee Discovery Widget',
                            'description': 'Interactive web component for displaying coffee products',
                            'mimeType': 'text/html+skybridge',
                            '_meta': widget_meta
                        }
                    ]
                },
                'id': jsonrpc_id
            }
        
        # Handle resources/read request
        elif jsonrpc_method == 'resources/read':
            uri = body_json.get('params', {}).get('uri')
            if uri == 'ui://widget/coffee-discovery.html':
                web_component_path = Path(__file__).parent / 'mcp_server' / 'web_component_simple.html'
                with open(web_component_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                widget_meta = {
                    'openai/outputTemplate': 'ui://widget/coffee-discovery.html',
                    'openai/widgetAccessible': True,
                    'openai/resultCanProduceWidget': True,
                    'openai/widgetPrefersBorder': True,
                    'openai/widgetDomain': 'https://chatgpt.com',
                    'openai/widgetCSP': {
                        'connect_domains': ['https://chatgpt.com'],
                        'resource_domains': ['https://*.oaistatic.com', 'https://images.unsplash.com']
                    }
                }
                
                response_data = {
                    'jsonrpc': '2.0',
                    'result': {
                        'contents': [
                            {
                                'uri': uri,
                                'mimeType': 'text/html+skybridge',
                                'text': content,
                                '_meta': widget_meta
                            }
                        ]
                    },
                    'id': jsonrpc_id
                }
            else:
                raise ValueError(f"Unknown resource URI: {uri}")
        
        else:
            logger.warning(f"Unknown JSON-RPC method: {jsonrpc_method}")
            response_data = {
                'jsonrpc': '2.0',
                'error': {
                    'code': -32601,
                    'message': f'Method not found: {jsonrpc_method}'
                },
                'id': jsonrpc_id
            }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
        
    except Exception as e:
        logger.error(f"Error processing MCP request: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'jsonrpc': '2.0',
                'error': {
                    'code': -32603,
                    'message': f'Internal error: {str(e)}'
                },
                'id': body_json.get('id') if isinstance(body_json, dict) else None
            })
        }

"""
Lambda handler for MCP server with OAuth 2.0 integration
Adapts the FastMCP server to work with API Gateway + Lambda
Routes OAuth requests and provides optional token validation
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

# Import OAuth handler
try:
    from oauth_handler import handle_oauth_request, validate_oauth_token
    logger.info("Successfully imported OAuth handler")
except ImportError as e:
    logger.error(f"Failed to import OAuth handler: {e}")
    raise


def lambda_handler(event, context):
    """
    Lambda handler that processes API Gateway requests and routes them to appropriate handlers.
    
    Routes OAuth requests to OAuth handler and MCP requests to MCP server.
    Supports optional OAuth token validation for MCP requests.
    """
    
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Extract request details from API Gateway event
    http_method = event.get('httpMethod', 'POST')
    path = event.get('path', '/')
    headers = event.get('headers', {})
    body = event.get('body', '')
    
    # Route OAuth requests to OAuth handler
    if is_oauth_request(path):
        logger.info(f"Routing OAuth request: {http_method} {path}")
        from oauth_handler import handle_oauth_request
        return handle_oauth_request(event, context)
    
    # Handle MCP requests (with optional OAuth validation)
    elif path == '/mcp':
        return handle_mcp_request(event, context, headers)
    
    # Unknown path
    else:
        logger.warning(f"Unknown path: {path}")
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Not found'})
        }


def is_oauth_request(path):
    """
    Check if the request path is an OAuth endpoint
    
    Args:
        path: Request path
        
    Returns:
        True if OAuth request, False otherwise
    """
    oauth_paths = [
        '/.well-known/oauth-authorization-server',
        '/.well-known/oauth-protected-resource', 
        '/oauth/authorize',
        '/oauth/token'
    ]
    return path in oauth_paths


def handle_mcp_request(event, context, headers):
    """
    Handle MCP requests with optional OAuth token validation
    
    Args:
        event: API Gateway event
        context: Lambda context
        headers: Request headers
        
    Returns:
        HTTP response
    """
    http_method = event.get('httpMethod', 'POST')
    path = event.get('path', '/')
    body = event.get('body', '')
    
    # Check for OAuth token in Authorization header (optional)
    authorization_header = headers.get('Authorization') or headers.get('authorization')
    user_context = None
    
    if authorization_header:
        logger.info("OAuth token found in request, validating...")
        from oauth_handler import validate_oauth_token
        user_context = validate_oauth_token(authorization_header)
        
        if user_context:
            logger.info(f"OAuth token validated for user: {user_context['username']}")
        else:
            logger.warning("Invalid OAuth token provided, returning 401")
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'WWW-Authenticate': 'Bearer error="invalid_token"'
                },
                'body': json.dumps({'error': 'invalid_token', 'error_description': 'The access token is invalid or expired'})
            }
    else:
        logger.warning("No OAuth token provided, returning 401")
        return {
            'statusCode': 401,
            'headers': {
                'Content-Type': 'application/json',
                'WWW-Authenticate': 'Bearer realm="MCP API"'
            },
            'body': json.dumps({'error': 'unauthorized', 'error_description': 'Authentication is required to access this endpoint'})
        }
    
    # Handle GET /mcp (discovery endpoint)
    if http_method == 'GET':
        return handle_mcp_discovery(event, context)
    
    # Handle POST /mcp (JSON-RPC requests)
    elif http_method == 'POST':
        return handle_mcp_jsonrpc(event, context, body, user_context)
    
    # Method not allowed
    else:
        return {
            'statusCode': 405,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Method not allowed. Use GET or POST.'})
        }


def handle_mcp_discovery(event, context):
    """
    Handle MCP discovery endpoint (GET /mcp)
    Returns OAuth discovery information for ChatGPT
    """
    # Import here to avoid circular imports
    from oauth_handler import handle_mcp_discovery
    return handle_mcp_discovery(event, context)


def handle_mcp_jsonrpc(event, context, body, user_context=None):
    """
    Handle MCP JSON-RPC requests (POST /mcp)
    
    Args:
        event: API Gateway event
        context: Lambda context  
        body: Request body
        user_context: Optional user context from OAuth validation
        
    Returns:
        HTTP response
    """
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
    
    # Process MCP request using FastMCP's stateless HTTP handler
    try:
        # FastMCP in stateless mode can handle JSON-RPC requests directly
        # The mcp instance has methods to handle the protocol
        
        # For now, we'll manually route to the appropriate handler
        # In production, FastMCP should expose a method to handle raw requests
        
        jsonrpc_method = body_json.get('method')
        jsonrpc_id = body_json.get('id')
        
        logger.info(f"Processing JSON-RPC method: {jsonrpc_method}")
        
        # Add user context to logging if available
        if user_context:
            logger.info(f"Request authenticated for user: {user_context['username']}")
        
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
                                'openai/outputTemplate': 'ui://widget/coffee-discovery-v2-1.html',
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
                                'openai/outputTemplate': 'ui://widget/coffee-discovery-v2-1.html',
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
                                'openai/outputTemplate': 'ui://widget/coffee-discovery-v2-1.html',
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
                        },
                        {
                            'name': 'add_to_cart',
                            'title': 'Add to Cart',
                            'description': 'Add a coffee product to the shopping cart.',
                            'inputSchema': {
                                'type': 'object',
                                'properties': {
                                    'product_id': {
                                        'type': 'string',
                                        'description': 'Unique product identifier'
                                    },
                                    'quantity': {
                                        'type': 'integer',
                                        'description': 'Number of items to add',
                                        'default': 1
                                    }
                                },
                                'required': ['product_id']
                            },
                            '_meta': {
                                'openai/outputTemplate': 'ui://widget/cart.html',
                                'openai/toolInvocation/invoking': 'Adding to cart...',
                                'openai/toolInvocation/invoked': 'Added to cart!',
                                'openai/widgetAccessible': True,
                                'openai/resultCanProduceWidget': True
                            },
                            'annotations': {
                                'destructiveHint': False,
                                'openWorldHint': False,
                                'readOnlyHint': False
                            }
                        },
                        {
                            'name': 'view_cart',
                            'title': 'View Cart',
                            'description': 'View current shopping cart contents.',
                            'inputSchema': {
                                'type': 'object',
                                'properties': {}
                            },
                            '_meta': {
                                'openai/outputTemplate': 'ui://widget/cart.html',
                                'openai/toolInvocation/invoking': 'Loading cart...',
                                'openai/toolInvocation/invoked': 'Cart loaded!',
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
                            'name': 'update_cart_quantity',
                            'title': 'Update Cart Quantity',
                            'description': 'Update the quantity of an item in the cart.',
                            'inputSchema': {
                                'type': 'object',
                                'properties': {
                                    'product_id': {
                                        'type': 'string',
                                        'description': 'Product identifier'
                                    },
                                    'quantity': {
                                        'type': 'integer',
                                        'description': 'New quantity (0 to remove item)'
                                    }
                                },
                                'required': ['product_id', 'quantity']
                            },
                            '_meta': {
                                'openai/outputTemplate': 'ui://widget/cart.html',
                                'openai/toolInvocation/invoking': 'Updating quantity...',
                                'openai/toolInvocation/invoked': 'Quantity updated!',
                                'openai/widgetAccessible': True,
                                'openai/resultCanProduceWidget': True
                            },
                            'annotations': {
                                'destructiveHint': False,
                                'openWorldHint': False,
                                'readOnlyHint': False
                            }
                        },
                        {
                            'name': 'remove_from_cart',
                            'title': 'Remove from Cart',
                            'description': 'Remove an item from the shopping cart.',
                            'inputSchema': {
                                'type': 'object',
                                'properties': {
                                    'product_id': {
                                        'type': 'string',
                                        'description': 'Product identifier to remove'
                                    }
                                },
                                'required': ['product_id']
                            },
                            '_meta': {
                                'openai/outputTemplate': 'ui://widget/cart.html',
                                'openai/toolInvocation/invoking': 'Removing item...',
                                'openai/toolInvocation/invoked': 'Item removed!',
                                'openai/widgetAccessible': True,
                                'openai/resultCanProduceWidget': True
                            },
                            'annotations': {
                                'destructiveHint': False,
                                'openWorldHint': False,
                                'readOnlyHint': False
                            }
                        },
                        {
                            'name': 'clear_cart',
                            'title': 'Clear Cart',
                            'description': 'Remove all items from the shopping cart.',
                            'inputSchema': {
                                'type': 'object',
                                'properties': {}
                            },
                            '_meta': {
                                'openai/outputTemplate': 'ui://widget/cart.html',
                                'openai/toolInvocation/invoking': 'Clearing cart...',
                                'openai/toolInvocation/invoked': 'Cart cleared!',
                                'openai/widgetAccessible': True,
                                'openai/resultCanProduceWidget': True
                            },
                            'annotations': {
                                'destructiveHint': True,
                                'openWorldHint': False,
                                'readOnlyHint': False
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
            from mcp_server.cart_tools import (
                add_to_cart_tool,
                view_cart_tool,
                update_cart_quantity_tool,
                remove_from_cart_tool,
                clear_cart_tool
            )
            
            # Pass user context to tools that might need it (for future use)
            tool_kwargs = {}
            if user_context:
                tool_kwargs['user_context'] = user_context
            
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
            elif tool_name == 'add_to_cart':
                result = add_to_cart_tool(
                    tool_arguments.get('product_id'),
                    tool_arguments.get('quantity', 1)
                )
            elif tool_name == 'view_cart':
                result = view_cart_tool()
            elif tool_name == 'update_cart_quantity':
                result = update_cart_quantity_tool(
                    tool_arguments.get('product_id'),
                    tool_arguments.get('quantity')
                )
            elif tool_name == 'remove_from_cart':
                result = remove_from_cart_tool(tool_arguments.get('product_id'))
            elif tool_name == 'clear_cart':
                result = clear_cart_tool()
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
            elif tool_name == 'add_to_cart':
                tool_meta = {
                    'openai/toolInvocation/invoking': 'Adding to cart...',
                    'openai/toolInvocation/invoked': 'Added to cart!'
                }
            elif tool_name == 'view_cart':
                tool_meta = {
                    'openai/toolInvocation/invoking': 'Loading cart...',
                    'openai/toolInvocation/invoked': 'Cart loaded!'
                }
            elif tool_name == 'update_cart_quantity':
                tool_meta = {
                    'openai/toolInvocation/invoking': 'Updating quantity...',
                    'openai/toolInvocation/invoked': 'Quantity updated!'
                }
            elif tool_name == 'remove_from_cart':
                tool_meta = {
                    'openai/toolInvocation/invoking': 'Removing item...',
                    'openai/toolInvocation/invoked': 'Item removed!'
                }
            elif tool_name == 'clear_cart':
                tool_meta = {
                    'openai/toolInvocation/invoking': 'Clearing cart...',
                    'openai/toolInvocation/invoked': 'Cart cleared!'
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
                'openai/outputTemplate': 'ui://widget/coffee-discovery-v2-1.html',
                'openai/widgetAccessible': True,
                'openai/resultCanProduceWidget': True
            }
            
            cart_widget_meta = {
                'openai/outputTemplate': 'ui://widget/cart.html',
                'openai/widgetAccessible': True,
                'openai/resultCanProduceWidget': True
            }
            
            response_data = {
                'jsonrpc': '2.0',
                'result': {
                    'resources': [
                        {
                            'uri': 'ui://widget/coffee-discovery-v2-1.html',
                            'name': 'Coffee Discovery Widget',
                            'title': 'Coffee Discovery Widget',
                            'description': 'Interactive web component for displaying coffee products',
                            'mimeType': 'text/html+skybridge',
                            '_meta': widget_meta
                        },
                        {
                            'uri': 'ui://widget/cart.html',
                            'name': 'Shopping Cart Widget',
                            'title': 'Shopping Cart Widget',
                            'description': 'Interactive web component for displaying shopping cart',
                            'mimeType': 'text/html+skybridge',
                            '_meta': cart_widget_meta
                        }
                    ]
                },
                'id': jsonrpc_id
            }
        
        # Handle resources/templates/list request (required by working example)
        elif jsonrpc_method == 'resources/templates/list':
            widget_meta = {
                'openai/outputTemplate': 'ui://widget/coffee-discovery-v2-1.html',
                'openai/widgetAccessible': True,
                'openai/resultCanProduceWidget': True
            }
            
            cart_widget_meta = {
                'openai/outputTemplate': 'ui://widget/cart.html',
                'openai/widgetAccessible': True,
                'openai/resultCanProduceWidget': True
            }
            
            response_data = {
                'jsonrpc': '2.0',
                'result': {
                    'resourceTemplates': [
                        {
                            'uriTemplate': 'ui://widget/coffee-discovery-v2-1.html',
                            'name': 'Coffee Discovery Widget',
                            'title': 'Coffee Discovery Widget',
                            'description': 'Interactive web component for displaying coffee products',
                            'mimeType': 'text/html+skybridge',
                            '_meta': widget_meta
                        },
                        {
                            'uriTemplate': 'ui://widget/cart.html',
                            'name': 'Shopping Cart Widget',
                            'title': 'Shopping Cart Widget',
                            'description': 'Interactive web component for displaying shopping cart',
                            'mimeType': 'text/html+skybridge',
                            '_meta': cart_widget_meta
                        }
                    ]
                },
                'id': jsonrpc_id
            }
        
        # Handle resources/read request
        elif jsonrpc_method == 'resources/read':
            uri = body_json.get('params', {}).get('uri')
            if uri == 'ui://widget/coffee-discovery-v2-1.html':
                web_component_path = Path(__file__).parent / 'mcp_server' / 'web_component_simple.html'
                with open(web_component_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Get CloudFront domain from environment variable
                cloudfront_domain = os.environ.get('CLOUDFRONT_DOMAIN', '')
                resource_domains = ['https://*.oaistatic.com', 'https://images.unsplash.com']
                if cloudfront_domain:
                    resource_domains.append(cloudfront_domain)
                
                widget_meta = {
                    'openai/outputTemplate': 'ui://widget/coffee-discovery-v2-1.html',
                    'openai/widgetAccessible': True,
                    'openai/resultCanProduceWidget': True,
                    'openai/widgetPrefersBorder': True,
                    'openai/widgetDomain': 'https://chatgpt.com',
                    'openai/widgetCSP': {
                        'connect_domains': ['https://chatgpt.com'],
                        'resource_domains': resource_domains
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
            elif uri == 'ui://widget/cart.html':
                cart_component_path = Path(__file__).parent / 'mcp_server' / 'cart_component.html'
                with open(cart_component_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                cart_widget_meta = {
                    'openai/outputTemplate': 'ui://widget/cart.html',
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
                                '_meta': cart_widget_meta
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
                                'openai/outputTemplate': 'ui://widget/coffee-discovery-v2-1.html',
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
                                'openai/outputTemplate': 'ui://widget/coffee-discovery-v2-1.html',
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
                                'openai/outputTemplate': 'ui://widget/coffee-discovery-v2-1.html',
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
                        },
                        {
                            'name': 'add_to_cart',
                            'title': 'Add to Cart',
                            'description': 'Add a coffee product to the shopping cart.',
                            'inputSchema': {
                                'type': 'object',
                                'properties': {
                                    'product_id': {
                                        'type': 'string',
                                        'description': 'Unique product identifier'
                                    },
                                    'quantity': {
                                        'type': 'integer',
                                        'description': 'Number of items to add',
                                        'default': 1
                                    }
                                },
                                'required': ['product_id']
                            },
                            '_meta': {
                                'openai/outputTemplate': 'ui://widget/cart.html',
                                'openai/toolInvocation/invoking': 'Adding to cart...',
                                'openai/toolInvocation/invoked': 'Added to cart!',
                                'openai/widgetAccessible': True,
                                'openai/resultCanProduceWidget': True
                            },
                            'annotations': {
                                'destructiveHint': False,
                                'openWorldHint': False,
                                'readOnlyHint': False
                            }
                        },
                        {
                            'name': 'view_cart',
                            'title': 'View Cart',
                            'description': 'View current shopping cart contents.',
                            'inputSchema': {
                                'type': 'object',
                                'properties': {}
                            },
                            '_meta': {
                                'openai/outputTemplate': 'ui://widget/cart.html',
                                'openai/toolInvocation/invoking': 'Loading cart...',
                                'openai/toolInvocation/invoked': 'Cart loaded!',
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
                            'name': 'update_cart_quantity',
                            'title': 'Update Cart Quantity',
                            'description': 'Update the quantity of an item in the cart.',
                            'inputSchema': {
                                'type': 'object',
                                'properties': {
                                    'product_id': {
                                        'type': 'string',
                                        'description': 'Product identifier'
                                    },
                                    'quantity': {
                                        'type': 'integer',
                                        'description': 'New quantity (0 to remove item)'
                                    }
                                },
                                'required': ['product_id', 'quantity']
                            },
                            '_meta': {
                                'openai/outputTemplate': 'ui://widget/cart.html',
                                'openai/toolInvocation/invoking': 'Updating quantity...',
                                'openai/toolInvocation/invoked': 'Quantity updated!',
                                'openai/widgetAccessible': True,
                                'openai/resultCanProduceWidget': True
                            },
                            'annotations': {
                                'destructiveHint': False,
                                'openWorldHint': False,
                                'readOnlyHint': False
                            }
                        },
                        {
                            'name': 'remove_from_cart',
                            'title': 'Remove from Cart',
                            'description': 'Remove an item from the shopping cart.',
                            'inputSchema': {
                                'type': 'object',
                                'properties': {
                                    'product_id': {
                                        'type': 'string',
                                        'description': 'Product identifier to remove'
                                    }
                                },
                                'required': ['product_id']
                            },
                            '_meta': {
                                'openai/outputTemplate': 'ui://widget/cart.html',
                                'openai/toolInvocation/invoking': 'Removing item...',
                                'openai/toolInvocation/invoked': 'Item removed!',
                                'openai/widgetAccessible': True,
                                'openai/resultCanProduceWidget': True
                            },
                            'annotations': {
                                'destructiveHint': False,
                                'openWorldHint': False,
                                'readOnlyHint': False
                            }
                        },
                        {
                            'name': 'clear_cart',
                            'title': 'Clear Cart',
                            'description': 'Remove all items from the shopping cart.',
                            'inputSchema': {
                                'type': 'object',
                                'properties': {}
                            },
                            '_meta': {
                                'openai/outputTemplate': 'ui://widget/cart.html',
                                'openai/toolInvocation/invoking': 'Clearing cart...',
                                'openai/toolInvocation/invoked': 'Cart cleared!',
                                'openai/widgetAccessible': True,
                                'openai/resultCanProduceWidget': True
                            },
                            'annotations': {
                                'destructiveHint': True,
                                'openWorldHint': False,
                                'readOnlyHint': False
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
            from mcp_server.cart_tools import (
                add_to_cart_tool,
                view_cart_tool,
                update_cart_quantity_tool,
                remove_from_cart_tool,
                clear_cart_tool
            )
            
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
            elif tool_name == 'add_to_cart':
                result = add_to_cart_tool(
                    tool_arguments.get('product_id'),
                    tool_arguments.get('quantity', 1)
                )
            elif tool_name == 'view_cart':
                result = view_cart_tool()
            elif tool_name == 'update_cart_quantity':
                result = update_cart_quantity_tool(
                    tool_arguments.get('product_id'),
                    tool_arguments.get('quantity')
                )
            elif tool_name == 'remove_from_cart':
                result = remove_from_cart_tool(tool_arguments.get('product_id'))
            elif tool_name == 'clear_cart':
                result = clear_cart_tool()
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
            elif tool_name == 'add_to_cart':
                tool_meta = {
                    'openai/toolInvocation/invoking': 'Adding to cart...',
                    'openai/toolInvocation/invoked': 'Added to cart!'
                }
            elif tool_name == 'view_cart':
                tool_meta = {
                    'openai/toolInvocation/invoking': 'Loading cart...',
                    'openai/toolInvocation/invoked': 'Cart loaded!'
                }
            elif tool_name == 'update_cart_quantity':
                tool_meta = {
                    'openai/toolInvocation/invoking': 'Updating quantity...',
                    'openai/toolInvocation/invoked': 'Quantity updated!'
                }
            elif tool_name == 'remove_from_cart':
                tool_meta = {
                    'openai/toolInvocation/invoking': 'Removing item...',
                    'openai/toolInvocation/invoked': 'Item removed!'
                }
            elif tool_name == 'clear_cart':
                tool_meta = {
                    'openai/toolInvocation/invoking': 'Clearing cart...',
                    'openai/toolInvocation/invoked': 'Cart cleared!'
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
                'openai/outputTemplate': 'ui://widget/coffee-discovery-v2-1.html',
                'openai/widgetAccessible': True,
                'openai/resultCanProduceWidget': True
            }
            
            cart_widget_meta = {
                'openai/outputTemplate': 'ui://widget/cart.html',
                'openai/widgetAccessible': True,
                'openai/resultCanProduceWidget': True
            }
            
            response_data = {
                'jsonrpc': '2.0',
                'result': {
                    'resources': [
                        {
                            'uri': 'ui://widget/coffee-discovery-v2-1.html',
                            'name': 'Coffee Discovery Widget',
                            'title': 'Coffee Discovery Widget',
                            'description': 'Interactive web component for displaying coffee products',
                            'mimeType': 'text/html+skybridge',
                            '_meta': widget_meta
                        },
                        {
                            'uri': 'ui://widget/cart.html',
                            'name': 'Shopping Cart Widget',
                            'title': 'Shopping Cart Widget',
                            'description': 'Interactive web component for displaying shopping cart',
                            'mimeType': 'text/html+skybridge',
                            '_meta': cart_widget_meta
                        }
                    ]
                },
                'id': jsonrpc_id
            }
        
        # Handle resources/templates/list request (required by working example)
        elif jsonrpc_method == 'resources/templates/list':
            widget_meta = {
                'openai/outputTemplate': 'ui://widget/coffee-discovery-v2-1.html',
                'openai/widgetAccessible': True,
                'openai/resultCanProduceWidget': True
            }
            
            cart_widget_meta = {
                'openai/outputTemplate': 'ui://widget/cart.html',
                'openai/widgetAccessible': True,
                'openai/resultCanProduceWidget': True
            }
            
            response_data = {
                'jsonrpc': '2.0',
                'result': {
                    'resourceTemplates': [
                        {
                            'uriTemplate': 'ui://widget/coffee-discovery-v2-1.html',
                            'name': 'Coffee Discovery Widget',
                            'title': 'Coffee Discovery Widget',
                            'description': 'Interactive web component for displaying coffee products',
                            'mimeType': 'text/html+skybridge',
                            '_meta': widget_meta
                        },
                        {
                            'uriTemplate': 'ui://widget/cart.html',
                            'name': 'Shopping Cart Widget',
                            'title': 'Shopping Cart Widget',
                            'description': 'Interactive web component for displaying shopping cart',
                            'mimeType': 'text/html+skybridge',
                            '_meta': cart_widget_meta
                        }
                    ]
                },
                'id': jsonrpc_id
            }
        
        # Handle resources/read request
        elif jsonrpc_method == 'resources/read':
            uri = body_json.get('params', {}).get('uri')
            if uri == 'ui://widget/coffee-discovery-v2-1.html':
                web_component_path = Path(__file__).parent / 'mcp_server' / 'web_component_simple.html'
                with open(web_component_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Get CloudFront domain from environment variable
                cloudfront_domain = os.environ.get('CLOUDFRONT_DOMAIN', '')
                resource_domains = ['https://*.oaistatic.com', 'https://images.unsplash.com']
                if cloudfront_domain:
                    resource_domains.append(cloudfront_domain)
                
                widget_meta = {
                    'openai/outputTemplate': 'ui://widget/coffee-discovery-v2-1.html',
                    'openai/widgetAccessible': True,
                    'openai/resultCanProduceWidget': True,
                    'openai/widgetPrefersBorder': True,
                    'openai/widgetDomain': 'https://chatgpt.com',
                    'openai/widgetCSP': {
                        'connect_domains': ['https://chatgpt.com'],
                        'resource_domains': resource_domains
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
            elif uri == 'ui://widget/cart.html':
                cart_component_path = Path(__file__).parent / 'mcp_server' / 'cart_component.html'
                with open(cart_component_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                cart_widget_meta = {
                    'openai/outputTemplate': 'ui://widget/cart.html',
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
                                '_meta': cart_widget_meta
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

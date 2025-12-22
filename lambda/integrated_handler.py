"""
Integrated Lambda handler for MCP server with OAuth 2.0 support
Combines OAuth authentication endpoints with MCP JSON-RPC functionality
Maintains backward compatibility with existing MCP functionality
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

# Import OAuth handler
try:
    from oauth_handler import handle_oauth_request, validate_oauth_token
    logger.info("Successfully imported OAuth handler")
except ImportError as e:
    logger.error(f"Failed to import OAuth handler: {e}")
    raise

# Import original MCP handler for fallback
try:
    from mcp_handler import lambda_handler as original_mcp_handler
    logger.info("Successfully imported original MCP handler")
except ImportError as e:
    logger.error(f"Failed to import original MCP handler: {e}")
    raise


def lambda_handler(event, context):
    """
    Integrated Lambda handler that routes requests between OAuth and MCP endpoints
    
    Routes:
    - OAuth endpoints: /.well-known/*, /oauth/* -> OAuth handler
    - GET /mcp -> OAuth discovery endpoint
    - POST /mcp -> MCP JSON-RPC with optional OAuth validation
    - All other paths -> 404
    
    Maintains backward compatibility with existing MCP functionality
    """
    
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Extract request details from API Gateway event
    http_method = event.get('httpMethod', 'POST')
    path = event.get('path', '/')
    headers = event.get('headers', {})
    
    logger.info(f"Original path: {path}")
    
    # Remove stage prefix if present (e.g., /prod/mcp -> /mcp)
    if path.startswith('/prod/'):
        path = path[5:]  # Remove '/prod' prefix
    elif path.startswith('/prod'):
        path = path[5:]  # Remove '/prod' prefix
    
    logger.info(f"Processing request: {http_method} {path}")
    
    # Route OAuth requests to OAuth handler
    if is_oauth_request(path, http_method):
        logger.info(f"Routing OAuth request: {http_method} {path}")
        return handle_oauth_request(event, context)
    
    # Handle MCP requests with optional OAuth validation
    elif path.endswith('/mcp'):
        return handle_mcp_request_with_oauth(event, context)
    
    # Unknown path
    else:
        logger.warning(f"Unknown path: {path}")
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Not found'})
        }


def is_oauth_request(path, method):
    """
    Determine if request should be routed to OAuth handler
    
    Args:
        path: Request path (already normalized by caller)
        method: HTTP method
        
    Returns:
        True if OAuth request, False otherwise
    """
    # GET /mcp is OAuth discovery endpoint
    if path.endswith('/mcp') and method == 'GET':
        return True
    
    # OAuth endpoints - use endswith() to match regardless of stage/mount prefix
    oauth_paths = [
        '/.well-known/oauth-authorization-server',
        '/.well-known/oauth-protected-resource',
        '/oauth/authorize',
        '/oauth/token',
        '/oauth/register'  # Add registration endpoint
    ]
    
    # Check if path ends with any OAuth path
    return any(path.endswith(oauth_path) for oauth_path in oauth_paths)


def handle_mcp_request_with_oauth(event, context):
    """
    Handle MCP requests with optional OAuth token validation
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        HTTP response
    """
    http_method = event.get('httpMethod', 'POST')
    headers = event.get('headers', {})
    path = event.get('path', '/')
    
    # Remove stage prefix if present (e.g., /prod/mcp -> /mcp)
    if path.startswith('/prod/'):
        path = path[5:]  # Remove '/prod' prefix
    elif path.startswith('/prod'):
        path = path[5:]  # Remove '/prod' prefix
    
    # Handle GET /mcp (OAuth discovery) - route to OAuth handler
    if http_method == 'GET' and path.endswith('/mcp'):
        logger.info("Routing GET /mcp to OAuth handler for discovery")
        return handle_oauth_request(event, context)
    
    # Handle POST /mcp (JSON-RPC) with optional OAuth validation
    elif http_method == 'POST' and path.endswith('/mcp'):
        return handle_mcp_jsonrpc_with_oauth(event, context, headers)
    
    # Method not allowed
    else:
        return {
            'statusCode': 405,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Method not allowed. Use GET or POST.'})
        }


def handle_mcp_jsonrpc_with_oauth(event, context, headers):
    """
    Handle MCP JSON-RPC requests with optional OAuth token validation
    
    Args:
        event: API Gateway event
        context: Lambda context
        headers: Request headers
        
    Returns:
        HTTP response
    """
    # Check for OAuth token in Authorization header (optional)
    authorization_header = headers.get('Authorization') or headers.get('authorization')
    user_context = None
    
    if authorization_header:
        logger.info("OAuth token found in request, validating...")
        user_context = validate_oauth_token(authorization_header)
        
        if user_context:
            logger.info(f"OAuth token validated for user: {user_context['username']}")
            # Add user context to event for potential use by tools
            event['oauth_user_context'] = user_context
        else:
            logger.warning("Invalid OAuth token provided")
            # Continue processing - maintains backward compatibility
            # In the future, you might want to return 401 for invalid tokens
    else:
        logger.info("No OAuth token provided, processing without authentication")
    
    # Process MCP request using original handler
    # The original handler will process the JSON-RPC request normally
    # User context is available in event['oauth_user_context'] if needed
    try:
        response = original_mcp_handler(event, context)
        
        # Log successful processing with authentication status
        if user_context:
            logger.info(f"MCP request processed successfully for authenticated user: {user_context['username']}")
        else:
            logger.info("MCP request processed successfully without authentication")
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing MCP request: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }


def get_user_context_from_event(event):
    """
    Helper function to extract OAuth user context from event
    Can be used by MCP tools that need user information
    
    Args:
        event: API Gateway event (may contain oauth_user_context)
        
    Returns:
        User context dict or None if not authenticated
    """
    return event.get('oauth_user_context')


def require_authentication(event):
    """
    Helper function to check if request is authenticated
    Can be used by MCP tools that require authentication
    
    Args:
        event: API Gateway event
        
    Returns:
        User context dict if authenticated
        
    Raises:
        ValueError: If not authenticated
    """
    user_context = get_user_context_from_event(event)
    if not user_context:
        raise ValueError("Authentication required")
    return user_context
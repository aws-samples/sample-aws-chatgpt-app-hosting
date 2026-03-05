"""
OAuth 2.0 handler module for ChatGPT authentication
Provides OAuth discovery endpoints and authorization flow
"""
import json
import logging
import os
import uuid
import time
from typing import Dict, Any, Optional
from urllib.parse import urlencode, parse_qs, unquote_plus
from cognito_auth import validate_credentials

logger = logging.getLogger(__name__)

# In-memory storage for authorization codes (simple implementation)
# In production, this should use a persistent store like DynamoDB
auth_codes: Dict[str, Dict[str, Any]] = {}

# Authorization code expiration time (10 minutes)
AUTH_CODE_EXPIRY_SECONDS = 600

# OAuth server configuration template
def get_oauth_config(base_url: str) -> Dict[str, Any]:
    """Get OAuth configuration with dynamic base URL"""
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/oauth/authorize",
        "token_endpoint": f"{base_url}/oauth/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],  # Advertise refresh_token for compatibility
        "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic", "none"],
        "code_challenge_methods_supported": ["S256", "plain"],
        "scopes_supported": ["openid", "profile", "read", "write"]  # Fixed scope consistency
    }

def _normalize_path(event: Dict[str, Any]) -> str:
    """
    Normalize path from API Gateway event, removing trailing slashes
    """
    path = event.get("path") or event.get("rawPath") or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return path


def get_external_base(event: Dict[str, Any]) -> str:
    """
    Extract the external base URL from the API Gateway event, including stage and MCP mount point
    """
    headers = event.get("headers") or {}
    host = headers.get("host") or headers.get("Host", "api.example.com")
    proto = headers.get("x-forwarded-proto") or "https"
    path = _normalize_path(event)
    
    # Log the path for debugging
    logger.info(f"get_external_base: path={path}, host={host}")
    
    # Build the base URL with proper stage handling
    # For API Gateway, we need to include the stage in the base URL
    base_url = f"{proto}://{host}"
    
    # For API Gateway REST API, the stage is included in the path
    # Extract stage from path like /prod/mcp -> stage is "prod"
    if path.startswith('/prod/'):
        base_url += "/prod/mcp"
    elif path.startswith('/stage/'):  # Handle other stages
        stage = path.split('/')[1]
        base_url += f"/{stage}/mcp"
    else:
        # Fallback - assume prod stage
        base_url += "/prod/mcp"
    
    logger.info(f"get_external_base: returning {base_url}")
    return base_url


def get_base_url_from_event(event: Dict[str, Any]) -> str:
    """
    Extract the base URL from the API Gateway event (legacy function for compatibility)
    """
    return get_external_base(event)


def handle_oauth_request(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Route OAuth requests to appropriate handlers based on path and method
    """
    path = _normalize_path(event)
    method = event.get('httpMethod', 'GET')
    
    logger.info(f"OAuth request: {method} {path}")
    
    # Periodically clean up expired authorization codes and OAuth tokens
    cleanup_expired_auth_codes()
    from cognito_auth import cleanup_expired_tokens
    cleanup_expired_tokens()
    
    try:
        # IMPORTANT: allow well-known and oauth endpoints to be nested under /mcp (and/or stage)
        # Use endswith() to match paths regardless of stage/mount prefix
        
        # OAuth discovery endpoints
        if path.endswith('/.well-known/oauth-authorization-server'):
            return handle_oauth_discovery(event, context)
        elif path.endswith('/.well-known/oauth-protected-resource'):
            return handle_resource_discovery(event, context)
        
        # OAuth authorization endpoints
        elif path.endswith('/oauth/authorize'):
            if method == 'GET':
                return handle_authorization_page(event, context)
            elif method == 'POST':
                return handle_authorization_approval(event, context)
            else:
                return {
                    'statusCode': 405,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Method not allowed'})
                }
        
        # OAuth token endpoint
        elif path.endswith('/oauth/token'):
            if method == 'POST':
                return handle_token_exchange(event, context)
            else:
                return {
                    'statusCode': 405,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Method not allowed'})
                }
        
        # OAuth Dynamic Client Registration endpoint (RFC 7591)
        elif path.endswith('/oauth/register'):
            if method == 'POST':
                return handle_client_registration(event, context)
            else:
                return {
                    'statusCode': 405,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Method not allowed'})
                }
        
        # MCP discovery endpoint (GET /mcp)
        elif path.endswith('/mcp') and method == 'GET':
            return handle_mcp_discovery(event, context)
        
        else:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Not found'})
            }
            
    except Exception as e:
        logger.error(f"Error handling OAuth request: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }

def handle_oauth_discovery(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle OAuth 2.0 authorization server metadata discovery
    Returns OAuth server configuration as per RFC 8414
    """
    base_url = get_external_base(event)
    oauth_config = get_oauth_config(base_url)
    
    metadata = {
        "issuer": oauth_config["issuer"],
        "authorization_endpoint": oauth_config["authorization_endpoint"],
        "token_endpoint": oauth_config["token_endpoint"],
        "registration_endpoint": f"{base_url}/oauth/register",  # RFC 7591 Dynamic Client Registration
        "response_types_supported": oauth_config["response_types_supported"],
        "grant_types_supported": oauth_config["grant_types_supported"],
        "token_endpoint_auth_methods_supported": oauth_config["token_endpoint_auth_methods_supported"],
        "code_challenge_methods_supported": oauth_config["code_challenge_methods_supported"],
        "scopes_supported": oauth_config["scopes_supported"]
    }
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(metadata)
    }

def handle_resource_discovery(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle OAuth 2.0 protected resource metadata discovery
    Returns resource server configuration
    """
    base_url = get_external_base(event)
    oauth_config = get_oauth_config(base_url)
    
    metadata = {
        "resource": base_url,  # The MCP server itself is the protected resource
        "authorization_servers": [base_url],
        "scopes_supported": oauth_config["scopes_supported"],
        "bearer_methods_supported": ["header"]
    }
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(metadata)
    }

def handle_authorization_page(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Display authorization page with HTML form for user approval
    """
    query_params = event.get('queryStringParameters') or {}
    
    # Validate required OAuth parameters
    client_id = query_params.get('client_id')
    redirect_uri = query_params.get('redirect_uri')
    response_type = query_params.get('response_type')
    state = query_params.get('state')
    scope = query_params.get('scope', 'openid profile')  # Capture requested scopes
    
    if not all([client_id, redirect_uri, response_type]):
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'invalid_request',
                'error_description': 'Missing required parameters'
            })
        }
    
    if response_type != 'code':
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'unsupported_response_type',
                'error_description': 'Only authorization code flow is supported'
            })
        }
    
    # Escape user-supplied OAuth params before rendering HTML to prevent XSS
    import html as html_lib
    html_content = generate_authorization_html(
        html_lib.escape(client_id),
        html_lib.escape(redirect_uri),
        html_lib.escape(state) if state else state,
        html_lib.escape(scope) if scope else scope
    )
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html',
            'Access-Control-Allow-Origin': '*'
        },
        'body': html_content  # nosemgrep: python.aws-lambda.security.tainted-html-response.tainted-html-response
    }

def handle_authorization_approval(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process authorization approval and generate authorization code
    Validates user credentials against Cognito and redirects to ChatGPT callback
    """
    try:
        # Parse form data from POST body
        body = event.get('body', '')
        if event.get('isBase64Encoded', False):
            import base64
            body = base64.b64decode(body).decode('utf-8')
        
        # Parse form parameters
        form_params = parse_qs(body)
        
        # Extract form fields (parse_qs returns lists, so get first value)
        def get_param(params: Dict, key: str) -> Optional[str]:
            values = params.get(key, [])
            return values[0] if values else None
        
        client_id = get_param(form_params, 'client_id')
        redirect_uri = get_param(form_params, 'redirect_uri')
        response_type = get_param(form_params, 'response_type')
        state = get_param(form_params, 'state')
        scope = get_param(form_params, 'scope') or 'openid profile'  # Capture scope from form
        username = get_param(form_params, 'username')
        password = get_param(form_params, 'password')
        action = get_param(form_params, 'action')
        
        # Validate required parameters
        if not all([client_id, redirect_uri, response_type, username, password, action]):
            logger.error("Missing required form parameters")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'invalid_request',
                    'error_description': 'Missing required parameters'
                })
            }
        
        # Handle denial
        if action == 'deny':
            logger.info(f"User denied authorization for client: {client_id}")
            return redirect_with_error(redirect_uri, 'access_denied', 
                                      'User denied authorization', state)
        
        # Handle approval
        if action != 'approve':
            logger.error(f"Invalid action: {action}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'invalid_request',
                    'error_description': 'Invalid action parameter'
                })
            }
        
        # Validate credentials against Cognito
        logger.info(f"Validating credentials for user: {username}")
        success, user_info = validate_credentials(username, password)
        
        if not success:
            logger.warning(f"Authentication failed for user: {username}")
            # Return error response with user-friendly message
            error_info = user_info if isinstance(user_info, dict) else {}
            error_message = error_info.get('message', 'Invalid username or password')
            
            return redirect_with_error(redirect_uri, 'access_denied', 
                                      error_message, state)
        
        # Generate authorization code
        auth_code = generate_authorization_code(
            username=username,
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            scope=scope,  # Pass the requested scope
            user_info=user_info
        )
        
        logger.info(f"Generated authorization code for user: {username}, client: {client_id}")
        
        # Redirect to ChatGPT callback with authorization code
        return redirect_with_code(redirect_uri, auth_code, state)
        
    except Exception as e:
        logger.error(f"Error processing authorization approval: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'server_error',
                'error_description': 'Internal server error processing authorization'
            })
        }

def handle_token_exchange(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle OAuth token exchange (authorization code for access token)
    Validates authorization code and returns access token backed by Cognito JWT
    """
    try:
        # Parse form data from POST body
        body = event.get('body', '')
        if event.get('isBase64Encoded', False):
            import base64
            body = base64.b64decode(body).decode('utf-8')
        
        # Parse form parameters
        form_params = parse_qs(body)
        
        # Extract required OAuth parameters
        def get_param(params: Dict, key: str) -> Optional[str]:
            values = params.get(key, [])
            return values[0] if values else None
        
        grant_type = get_param(form_params, 'grant_type')
        code = get_param(form_params, 'code')
        redirect_uri = get_param(form_params, 'redirect_uri')
        client_id = get_param(form_params, 'client_id')
        
        # Validate required parameters
        if not all([grant_type, code, redirect_uri, client_id]):
            logger.error("Missing required token exchange parameters")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'invalid_request',
                    'error_description': 'Missing required parameters'
                })
            }
        
        # Validate grant type
        if grant_type != 'authorization_code':
            logger.error(f"Unsupported grant type: {grant_type}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'unsupported_grant_type',
                    'error_description': 'Only authorization_code grant type is supported'
                })
            }
        
        # Validate and retrieve authorization code
        code_info = get_authorization_code_info(code)
        if not code_info:
            logger.error(f"Invalid or expired authorization code: {code[:16]}...")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'invalid_grant',
                    'error_description': 'Invalid or expired authorization code'
                })
            }
        
        # Validate client_id matches
        if code_info['client_id'] != client_id:
            logger.error(f"Client ID mismatch: expected {code_info['client_id']}, got {client_id}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'invalid_client',
                    'error_description': 'Client ID does not match authorization code'
                })
            }
        
        # Validate redirect_uri matches
        if code_info['redirect_uri'] != redirect_uri:
            logger.error(f"Redirect URI mismatch: expected {code_info['redirect_uri']}, got {redirect_uri}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'invalid_grant',
                    'error_description': 'Redirect URI does not match authorization code'
                })
            }
        
        # Mark authorization code as used (single-use only)
        mark_authorization_code_used(code)
        
        # Generate OAuth access token backed by Cognito JWT
        from cognito_auth import generate_oauth_access_token
        
        user_info = code_info['user_info']
        access_token = generate_oauth_access_token(user_info)
        
        # Calculate token expiration (use Cognito token expiration)
        expires_in = user_info['expires_at'] - int(time.time())
        if expires_in <= 0:
            expires_in = 3600  # Default to 1 hour if calculation fails
        
        # Return OAuth token response with the originally requested scope
        token_response = {
            'access_token': access_token,
            'token_type': 'Bearer',
            'expires_in': expires_in,
            'scope': code_info['scope']  # Use the scope from the authorization request
        }
        
        logger.info(f"Successfully exchanged authorization code for access token for user: {user_info['username']}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Cache-Control': 'no-store',
                'Pragma': 'no-cache'
            },
            'body': json.dumps(token_response)
        }
        
    except Exception as e:
        logger.error(f"Error during token exchange: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'server_error',
                'error_description': 'Internal server error during token exchange'
            })
        }

def handle_mcp_discovery(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle MCP discovery endpoint (GET /mcp)
    Returns MCP protocol information with OAuth capabilities for ChatGPT
    """
    base_url = get_external_base(event)
    oauth_config = get_oauth_config(base_url)
    
    # Return MCP protocol response with OAuth capabilities
    discovery_info = {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {},
            "oauth": {
                "authorizationUrl": oauth_config["authorization_endpoint"],
                "tokenUrl": oauth_config["token_endpoint"],
                "grantTypes": ["authorization_code"],
                "responseTypes": ["code"]
            }
        },
        "serverInfo": {
            "name": "coffee-discovery-mcp-server",
            "version": "1.0.0"
        }
    }
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(discovery_info)
    }

def generate_authorization_html(client_id: str, redirect_uri: str, state: Optional[str], scope: Optional[str] = None) -> str:
    """
    Generate HTML authorization page with form for user credentials
    """
    state_input = f'<input type="hidden" name="state" value="{state}">' if state else ''
    scope_input = f'<input type="hidden" name="scope" value="{scope}">' if scope else ''
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Coffee Discovery - Authorization</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 400px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .auth-container {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #8B4513;
            text-align: center;
            margin-bottom: 10px;
        }}
        .subtitle {{
            text-align: center;
            color: #666;
            margin-bottom: 30px;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        label {{
            display: block;
            margin-bottom: 5px;
            font-weight: 500;
            color: #333;
        }}
        input[type="text"], input[type="password"] {{
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
            box-sizing: border-box;
        }}
        input[type="text"]:focus, input[type="password"]:focus {{
            outline: none;
            border-color: #8B4513;
            box-shadow: 0 0 0 2px rgba(139, 69, 19, 0.2);
        }}
        .btn-group {{
            display: flex;
            gap: 10px;
            margin-top: 30px;
        }}
        button {{
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 4px;
            font-size: 16px;
            cursor: pointer;
            font-weight: 500;
        }}
        .btn-approve {{
            background-color: #8B4513;
            color: white;
        }}
        .btn-approve:hover {{
            background-color: #A0522D;
        }}
        .btn-deny {{
            background-color: #6c757d;
            color: white;
        }}
        .btn-deny:hover {{
            background-color: #5a6268;
        }}
        .client-info {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
            border-left: 4px solid #8B4513;
        }}
        .error {{
            color: #dc3545;
            font-size: 14px;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="auth-container">
        <h1>☕ Coffee Discovery</h1>
        <p class="subtitle">Authorization Required</p>
        
        <div class="client-info">
            <strong>ChatGPT</strong> is requesting access to your Coffee Discovery account.
            <br><small>Client ID: {client_id}</small>
        </div>
        
        <form method="POST" action="">
            <input type="hidden" name="client_id" value="{client_id}">
            <input type="hidden" name="redirect_uri" value="{redirect_uri}">
            <input type="hidden" name="response_type" value="code">
            {state_input}
            {scope_input}
            
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required 
                       placeholder="Enter your Cognito username">
            </div>
            
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required 
                       placeholder="Enter your password">
            </div>
            
            <div class="btn-group">
                <button type="submit" name="action" value="approve" class="btn-approve">
                    Authorize
                </button>
                <button type="submit" name="action" value="deny" class="btn-deny">
                    Deny
                </button>
            </div>
        </form>
    </div>
</body>
</html>
"""
    return html

def generate_authorization_code(username: str, client_id: str, redirect_uri: str, 
                              state: Optional[str], scope: str, user_info: Dict[str, Any]) -> str:
    """
    Generate and store authorization code for OAuth flow
    
    Args:
        username: Authenticated username
        client_id: OAuth client ID
        redirect_uri: Callback URI for the client
        state: Optional state parameter from client
        scope: Requested OAuth scopes
        user_info: User information from Cognito authentication
        
    Returns:
        Authorization code string
    """
    # Generate unique authorization code
    auth_code = f"auth_{uuid.uuid4().hex}"
    
    # Store authorization code with metadata
    auth_codes[auth_code] = {
        'username': username,
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'state': state,
        'scope': scope,  # Store the requested scope
        'user_info': user_info,
        'created_at': int(time.time()),
        'expires_at': int(time.time()) + AUTH_CODE_EXPIRY_SECONDS,
        'used': False
    }
    
    logger.info(f"Generated authorization code for user {username}, expires in {AUTH_CODE_EXPIRY_SECONDS} seconds")
    return auth_code


def redirect_with_code(redirect_uri: str, auth_code: str, state: Optional[str]) -> Dict[str, Any]:
    """
    Create redirect response with authorization code
    
    Args:
        redirect_uri: Client callback URI
        auth_code: Generated authorization code
        state: Optional state parameter to include
        
    Returns:
        HTTP redirect response
    """
    # Build query parameters for redirect
    params = {'code': auth_code}
    if state:
        params['state'] = state
    
    # Construct redirect URL
    redirect_url = f"{redirect_uri}?{urlencode(params)}"
    
    logger.info(f"Redirecting to: {redirect_url}")
    
    return {
        'statusCode': 302,
        'headers': {
            'Location': redirect_url,
            'Content-Type': 'text/html'
        },
        'body': f'<html><body>Redirecting to <a href="{redirect_url}">{redirect_url}</a></body></html>'
    }


def redirect_with_error(redirect_uri: str, error: str, error_description: str, 
                       state: Optional[str]) -> Dict[str, Any]:
    """
    Create redirect response with OAuth error
    
    Args:
        redirect_uri: Client callback URI
        error: OAuth error code
        error_description: Human-readable error description
        state: Optional state parameter to include
        
    Returns:
        HTTP redirect response
    """
    # Build error parameters for redirect
    params = {
        'error': error,
        'error_description': error_description
    }
    if state:
        params['state'] = state
    
    # Construct redirect URL
    redirect_url = f"{redirect_uri}?{urlencode(params)}"
    
    logger.info(f"Redirecting with error to: {redirect_url}")
    
    return {
        'statusCode': 302,
        'headers': {
            'Location': redirect_url,
            'Content-Type': 'text/html'
        },
        'body': f'<html><body>Authorization failed. Redirecting to <a href="{redirect_url}">{redirect_url}</a></body></html>'
    }


def get_authorization_code_info(auth_code: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve and validate authorization code information
    
    Args:
        auth_code: Authorization code to look up
        
    Returns:
        Authorization code info dict or None if invalid/expired
    """
    if not auth_code:
        return None
    
    code_info = auth_codes.get(auth_code)
    if not code_info:
        logger.warning(f"Authorization code not found: {auth_code[:16]}...")
        return None
    
    # Check if code has expired
    if int(time.time()) > code_info['expires_at']:
        logger.warning(f"Authorization code expired: {auth_code[:16]}...")
        # Clean up expired code
        del auth_codes[auth_code]
        return None
    
    # Check if code has already been used
    if code_info['used']:
        logger.warning(f"Authorization code already used: {auth_code[:16]}...")
        # Clean up used code
        del auth_codes[auth_code]
        return None
    
    return code_info


def mark_authorization_code_used(auth_code: str) -> bool:
    """
    Mark authorization code as used (single-use only)
    
    Args:
        auth_code: Authorization code to mark as used
        
    Returns:
        True if successfully marked, False if code not found
    """
    if auth_code in auth_codes:
        auth_codes[auth_code]['used'] = True
        logger.info(f"Marked authorization code as used: {auth_code[:16]}...")
        return True
    return False


def cleanup_expired_auth_codes() -> int:
    """
    Clean up expired authorization codes from memory
    Should be called periodically to prevent memory leaks
    
    Returns:
        Number of codes cleaned up
    """
    current_time = int(time.time())
    expired_codes = [
        code for code, info in auth_codes.items()
        if current_time > info['expires_at'] or info['used']
    ]
    
    for code in expired_codes:
        del auth_codes[code]
    
    if expired_codes:
        logger.info(f"Cleaned up {len(expired_codes)} expired/used authorization codes")
    
    return len(expired_codes)


def validate_oauth_token(authorization_header: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Validate OAuth Bearer token from Authorization header
    
    Args:
        authorization_header: Authorization header value (e.g., "Bearer token123")
        
    Returns:
        User information dict if token is valid, None otherwise
    """
    if not authorization_header:
        return None
    
    if not authorization_header.startswith('Bearer '):
        return None
    
    # Extract token from header
    oauth_token = authorization_header[7:]  # Remove 'Bearer ' prefix
    
    # Validate token using Cognito authenticator
    from cognito_auth import validate_oauth_access_token
    
    try:
        is_valid, user_info = validate_oauth_access_token(oauth_token)
        
        if is_valid and user_info:
            logger.info(f"OAuth token validated for user: {user_info['username']}")
            return user_info
        else:
            logger.warning(f"Invalid OAuth token: {oauth_token[:16]}...")
            return None
            
    except Exception as e:
        logger.error(f"Error validating OAuth token: {str(e)}", exc_info=True)
        return None

def _normalize_list(val):
    """Normalize a value to a list, handling strings and None"""
    if val is None:
        return None
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return [val]
    return None

def handle_client_registration(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle OAuth 2.0 Dynamic Client Registration (RFC 7591)
    Allows clients like ChatGPT to automatically register themselves
    """
    try:
        # Parse the registration request
        body = event.get('body', '{}')
        if event.get('isBase64Encoded', False):
            import base64
            body = base64.b64decode(body).decode('utf-8')
        
        try:
            registration_request = json.loads(body)
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'invalid_request',
                    'error_description': 'Invalid JSON in request body'
                })
            }
        
        # Log the incoming registration request for debugging
        logger.info("DCR request body: %s", json.dumps(registration_request))
        
        # Extract client metadata
        client_name = registration_request.get('client_name', 'Unknown Client')
        redirect_uris = registration_request.get('redirect_uris', [])
        response_types = registration_request.get('response_types', ['code'])
        scope = registration_request.get('scope', 'openid profile read write')
        
        # Validate redirect URIs
        if not redirect_uris:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'invalid_redirect_uri',
                    'error_description': 'At least one redirect_uri is required'
                })
            }
        
        # Handle grant_types with permissive validation
        SUPPORTED_GRANTS = {"authorization_code", "refresh_token"}  # Allow refresh_token for future compatibility
        
        req_grants = _normalize_list(registration_request.get("grant_types"))
        
        # If omitted, default to authorization_code
        if not req_grants:
            req_grants = ["authorization_code"]
        
        # If authorization_code isn't present at all, reject
        if "authorization_code" not in req_grants:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'invalid_client_metadata',
                    'error_description': 'grant_types must include authorization_code'
                })
            }
        
        # Clamp to the grants we actually support (don't error just because extras were sent)
        registered_grants = [g for g in req_grants if g in SUPPORTED_GRANTS]
        if not registered_grants:
            registered_grants = ["authorization_code"]
        
        logger.info(f"Client requested grant_types: {req_grants}, registered with: {registered_grants}")
        
        # Generate unique client credentials
        client_id = f"dyn_{uuid.uuid4().hex[:16]}"
        client_secret = None  # Public client (no secret)
        
        # Log client type for debugging (but always use unique ID)
        client_type = "unknown"
        if any('chatgpt.com' in uri for uri in redirect_uris):
            client_type = "chatgpt"
            logger.info(f"Registering ChatGPT client with unique ID: {client_id}")
        
        # Create client registration response
        registration_response = {
            'client_id': client_id,
            'client_name': client_name,
            'redirect_uris': redirect_uris,
            'grant_types': registered_grants,  # Use the clamped grant types
            'response_types': response_types,
            'scope': scope,
            'token_endpoint_auth_method': 'none',  # Public client
            'client_id_issued_at': int(time.time()),
            'client_secret_expires_at': 0  # No secret issued
        }
        
        # Log the registration
        logger.info(f"Registered OAuth client: {client_id} ({client_name}) with redirect URIs: {redirect_uris}")
        
        # Store client registration in DynamoDB for persistence
        try:
            import boto3
            dynamodb = boto3.resource('dynamodb')
            oauth_clients_table_name = os.environ.get('DYNAMODB_OAUTH_CLIENTS_TABLE', 'oauth-clients')
            table = dynamodb.Table(oauth_clients_table_name)
            
            # Store client registration (expires in 1 year)
            expires_at = int(time.time()) + (365 * 24 * 60 * 60)  # 1 year from now
            
            table.put_item(
                Item={
                    'client_id': client_id,
                    'client_name': client_name,
                    'redirect_uris': redirect_uris,
                    'grant_types': registered_grants,  # Use the clamped grant types
                    'response_types': response_types,
                    'scope': scope,
                    'token_endpoint_auth_method': 'none',
                    'client_id_issued_at': registration_response['client_id_issued_at'],
                    'client_secret_expires_at': 0,
                    'expires_at': expires_at,
                    'client_type': client_type
                }
            )
            logger.info(f"Stored client registration in DynamoDB: {client_id}")
            
        except Exception as db_error:
            logger.error(f"Failed to store client registration in DynamoDB: {str(db_error)}")
            # Continue anyway - registration still works, just not persistent
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Cache-Control': 'no-store',
                'Pragma': 'no-cache'
            },
            'body': json.dumps(registration_response)
        }
        
    except Exception as e:
        logger.error(f"Error during client registration: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'server_error',
                'error_description': 'Internal server error during client registration'
            })
        }
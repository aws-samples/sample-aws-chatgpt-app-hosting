# Design Document

## Overview

This design adds minimal OAuth 2.0 endpoints to the existing MCP Lambda function to enable ChatGPT authentication while leveraging the existing Cognito User Pool. The implementation reuses the OAuth pattern from the reference implementation but validates credentials against Cognito instead of in-memory storage.

## Architecture

### Current State
- API Gateway → Lambda (MCP Server) 
- Cognito User Pool (existing)
- `/mcp` endpoint (no authentication)

### Target State  
- API Gateway → Lambda (MCP Server + OAuth endpoints)
- Cognito User Pool (unchanged)
- `/mcp` endpoint (supports OAuth Bearer tokens)
- New OAuth endpoints: `/.well-known/*`, `/oauth/authorize`, `/oauth/token`

## Components and Interfaces

### OAuth Endpoints (New)
- `GET /.well-known/oauth-authorization-server` - OAuth discovery metadata
- `GET /.well-known/oauth-protected-resource` - Resource server metadata  
- `GET /oauth/authorize` - Authorization page (HTML form)
- `POST /oauth/authorize` - Process authorization, generate code
- `POST /oauth/token` - Exchange code for access token

### MCP Endpoint (Modified)
- `GET /mcp` - Returns OAuth discovery info (no auth required)
- `POST /mcp` - Processes MCP requests (supports OAuth Bearer tokens)

### Cognito Integration
- Use existing Cognito User Pool for credential validation
- Generate temporary OAuth codes that map to Cognito users
- Issue access tokens that contain Cognito JWT tokens

## Data Models

### Authorization Code Storage
```python
# Temporary in-memory storage (simple implementation)
auth_codes = {
    "code123": {
        "cognito_username": "testuser",
        "client_id": "chatgpt_client", 
        "redirect_uri": "https://chatgpt.com/callback",
        "state": "xyz789",
        "expires_at": 1234567890,
        "used": False
    }
}
```

### Access Token Storage  
```python
# Map OAuth tokens to Cognito JWT tokens
access_tokens = {
    "oauth_token_abc": {
        "cognito_jwt": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...",
        "username": "testuser",
        "expires_at": 1234567890
    }
}
```

## Error Handling

- Invalid OAuth requests return standard OAuth error responses
- Cognito authentication failures return OAuth `invalid_grant` errors
- Expired tokens return `401 Unauthorized` 
- Malformed requests return `400 Bad Request`

## Testing Strategy

### Manual Testing
- Test OAuth flow end-to-end with ChatGPT
- Verify existing MCP functionality remains unchanged
- Test with valid and invalid Cognito credentials
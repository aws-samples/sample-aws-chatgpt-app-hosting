# Implementation Plan

- [x] 1. Create OAuth handler module
  - Create `lambda/oauth_handler.py` with OAuth endpoint routing
  - Implement OAuth discovery endpoints (/.well-known/*)
  - Implement authorization page with HTML form
  - _Requirements: 1.1, 1.2_

- [x] 2. Create Cognito authentication module  
  - Create `lambda/cognito_auth.py` for Cognito integration
  - Implement credential validation against existing User Pool
  - Implement JWT token operations for OAuth token backing
  - _Requirements: 2.1, 2.2_

- [x] 3. Implement OAuth authorization flow
  - Add authorization code generation and storage
  - Add authorization approval processing
  - Add redirect handling to ChatGPT callback
  - _Requirements: 1.2, 1.3_

- [x] 4. Implement OAuth token exchange
  - Add token endpoint for authorization code exchange
  - Add access token generation backed by Cognito JWT
  - Add token validation for MCP requests
  - _Requirements: 1.4, 2.2_

- [x] 5. Integrate OAuth with existing MCP handler
  - Modify `lambda/mcp_handler.py` to route OAuth requests
  - Add optional OAuth token validation to /mcp endpoint
  - Ensure backward compatibility with existing functionality
  - _Requirements: 1.5, 3.1, 3.2, 3.3_

- [x] 6. Update API Gateway routes
  - Add new OAuth endpoint routes to API Gateway configuration
  - Update CDK infrastructure to include OAuth paths
  - Deploy and test OAuth endpoint accessibility
  - _Requirements: 1.1_

- [ ] 7. Manual testing and validation
  - Test OAuth discovery endpoints return correct metadata
  - Test authorization flow with valid Cognito credentials
  - Test token exchange and MCP request processing
  - Verify existing MCP functionality remains unchanged
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 3.1, 3.2, 3.3_
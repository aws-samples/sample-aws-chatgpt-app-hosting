# Requirements Document

## Introduction

Add OAuth 2.0 endpoints to the existing Coffee Discovery MCP server to enable ChatGPT authentication while maintaining compatibility with the existing Cognito User Pool infrastructure. This is a minimal implementation focused on getting ChatGPT OAuth working without adding new functionality.

## Glossary

- **OAuth Server**: The OAuth 2.0 authorization server endpoints added to the Lambda function
- **Cognito User Pool**: The existing AWS Cognito User Pool for user authentication
- **MCP Server**: The existing Model Context Protocol server Lambda function
- **ChatGPT**: The client application that will authenticate via OAuth 2.0
- **API Gateway**: The existing AWS API Gateway that routes requests to the Lambda function

## Requirements

### Requirement 1

**User Story:** As a ChatGPT user, I want to authenticate with the MCP server using OAuth 2.0, so that I can access the coffee discovery tools securely.

#### Acceptance Criteria

1. WHEN ChatGPT requests OAuth discovery information, THE OAuth Server SHALL return OAuth 2.0 authorization server metadata
2. WHEN ChatGPT initiates authorization, THE OAuth Server SHALL display an authorization page for user approval
3. WHEN a user approves authorization, THE OAuth Server SHALL generate an authorization code and redirect to ChatGPT
4. WHEN ChatGPT exchanges an authorization code for tokens, THE OAuth Server SHALL validate the code and return access tokens
5. WHEN ChatGPT makes MCP requests with valid tokens, THE OAuth Server SHALL process the requests successfully

### Requirement 2

**User Story:** As a system administrator, I want OAuth tokens to be backed by Cognito authentication, so that the existing user management system remains intact.

#### Acceptance Criteria

1. WHEN generating OAuth tokens, THE OAuth Server SHALL validate user credentials against the existing Cognito User Pool
2. WHEN validating OAuth access tokens, THE OAuth Server SHALL verify the underlying Cognito JWT token validity
3. WHEN OAuth tokens expire, THE OAuth Server SHALL require re-authentication through Cognito

### Requirement 3

**User Story:** As a developer, I want the existing MCP functionality to remain unchanged, so that current integrations continue to work.

#### Acceptance Criteria

1. WHEN the existing `/mcp` endpoint receives requests without OAuth headers, THE MCP Server SHALL continue processing requests as before
2. WHEN the existing Cognito-based tools make requests, THE MCP Server SHALL continue to work without modification
3. WHEN OAuth endpoints are added, THE MCP Server SHALL maintain all existing tool functionality
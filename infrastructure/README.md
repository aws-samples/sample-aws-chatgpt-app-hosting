# Coffee Discovery CDK Infrastructure

This directory contains the AWS CDK infrastructure code for the Coffee Discovery ChatGPT App.

## Prerequisites

- AWS CLI configured with appropriate credentials
- AWS CDK CLI installed: `npm install -g aws-cdk`
- Python 3.11 or higher
- Docker running (required for building the MCP server container)

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Deployment

1. Bootstrap CDK (first time only):
```bash
cdk bootstrap
```

2. Synthesize CloudFormation template (optional, for verification):
```bash
cdk synth
```

3. Deploy the stack:
```bash
cdk deploy
```

4. Note the outputs from the deployment - you'll need these values for:
   - Loading the product catalog
   - Creating test users
   - Configuring the ChatGPT connector

## Stack Resources

The CDK stack creates:

- **Cognito User Pool**: OAuth 2.0 authentication provider
- **Cognito App Client**: Public client for ChatGPT integration
- **OpenSearch Serverless Collection**: Vector search for coffee products
- **AgentCore Runtime**: Hosts the MCP server container
- **IAM Roles**: Execution role with permissions for OpenSearch and Bedrock
- **ECR Repository**: Automatically created for the Docker image

## Outputs

After deployment, the stack outputs:

- `CognitoUserPoolId`: User pool ID for creating test users
- `CognitoClientId`: Client ID for OAuth configuration
- `CognitoDiscoveryUrl`: OIDC discovery URL for token validation
- `OpenSearchEndpoint`: Endpoint for loading product data
- `AgentCoreRuntimeArn`: Runtime ARN for reference
- `AgentCoreInvocationUrl`: Endpoint URL for ChatGPT connector

## Cleanup

To destroy all resources:
```bash
cdk destroy
```

## Notes

- The Docker image is built from the `../mcp_server` directory
- The image is automatically pushed to ECR during deployment
- The stack uses ARM64 platform for optimal AgentCore Runtime performance
- OpenSearch collection uses on-demand capacity (serverless)

#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.coffee_discovery_stack import CoffeeDiscoveryStack
from stacks.image_hosting_stack import ImageHostingStack

app = cdk.App()

# Create image hosting stack (S3 + CloudFront)
image_hosting_stack = ImageHostingStack(
    app,
    "ImageHostingStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region=os.getenv('CDK_DEFAULT_REGION', 'us-east-1')
    ),
    description="S3 and CloudFront infrastructure for product images"
)

# Create main application stack
coffee_stack = CoffeeDiscoveryStack(
    app,
    "ChatGPTAppAWSStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region=os.getenv('CDK_DEFAULT_REGION', 'us-east-1')
    ),
    description="ChatGPT App AWS - MCP Server with AgentCore Runtime"
)

# Add dependency so coffee stack can reference image hosting resources
coffee_stack.add_dependency(image_hosting_stack)

app.synth()

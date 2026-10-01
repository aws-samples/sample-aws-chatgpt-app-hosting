#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.image_hosting_stack import ImageHostingStack
from stacks.agentcore_stack import AgentCoreStack

app = cdk.App()

env = cdk.Environment(
    account=os.getenv('CDK_DEFAULT_ACCOUNT'),
    region=os.getenv('CDK_DEFAULT_REGION', 'us-east-1')
)

# Create image hosting stack (S3 + CloudFront)
image_hosting_stack = ImageHostingStack(
    app,
    "ImageHostingStack",
    env=env,
    description="S3 and CloudFront infrastructure for product images"
)

# Create the AgentCore stack (Gateway + Runtime + OpenSearch + Cart + Cognito M2M)
agentcore_stack = AgentCoreStack(
    app,
    "AgentCoreStack",
    env=env,
    description="ChatGPT Coffee App - AgentCore Gateway + Runtime (Part 2)"
)

# AgentCore stack imports the CloudFront domain from the image hosting stack
agentcore_stack.add_dependency(image_hosting_stack)

app.synth()

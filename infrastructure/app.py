#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.coffee_discovery_stack import CoffeeDiscoveryStack

app = cdk.App()

CoffeeDiscoveryStack(
    app,
    "ChatGPTAppAWSStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region=os.getenv('CDK_DEFAULT_REGION', 'us-west-2')
    ),
    description="ChatGPT App AWS - MCP Server with AgentCore Runtime"
)

app.synth()

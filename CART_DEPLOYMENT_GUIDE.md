# Shopping Cart Feature Deployment Guide

This guide describes the steps needed to deploy the shopping cart feature to AWS.

## Prerequisites

- AWS CLI configured with appropriate credentials
- AWS CDK CLI installed: `npm install -g aws-cdk`
- Python 3.11 or higher
- Docker running (required for building the Lambda function)

## Infrastructure Changes

The shopping cart feature adds the following infrastructure components:

### 1. DynamoDB Table

A new DynamoDB table `coffee-cart` has been added with:
- **Partition Key**: `user_id` (STRING)
- **Billing Mode**: PAY_PER_REQUEST (on-demand)
- **TTL Attribute**: `ttl` (for automatic cleanup of old carts)
- **Removal Policy**: DESTROY (for development)

### 2. Lambda Permissions

The Lambda execution role has been granted:
- `dynamodb:GetItem` - Read cart data
- `dynamodb:PutItem` - Write cart data
- `dynamodb:DeleteItem` - Delete cart data
- `dynamodb:Query` - Query cart data
- `dynamodb:Scan` - Scan cart data

### 3. Environment Variables

The Lambda function now includes:
- `DYNAMODB_CART_TABLE`: Set to `coffee-cart`

### 4. New Lambda Code

The following new modules have been added to the Lambda deployment package:
- `cart_repository.py` - DynamoDB data access layer
- `cart_manager.py` - Business logic for cart operations
- `cart_tools.py` - MCP tool implementations
- `cart_component.html` - Web component for cart display

### 5. MCP Server Updates

The MCP server (`server.py`) now registers:
- 5 new cart tools: `add_to_cart`, `view_cart`, `update_cart_quantity`, `remove_from_cart`, `clear_cart`
- 1 new web component resource: `ui://widget/cart.html`

## Deployment Steps

### Step 1: Review Changes

Run CDK diff to see what will be deployed:

```bash
cd infrastructure
cdk diff
```

Expected changes:
- New DynamoDB table: `CoffeeCartTable`
- Updated Lambda function with new code and environment variables
- Updated IAM role with DynamoDB permissions

### Step 2: Deploy Stack

Deploy the updated stack:

```bash
cdk deploy
```

This will:
1. Create the DynamoDB table
2. Update the Lambda function with new code
3. Grant necessary permissions
4. Update environment variables

### Step 3: Verify Deployment

After deployment, verify:

1. **DynamoDB Table Exists**:
   ```bash
   aws dynamodb describe-table --table-name coffee-cart
   ```

2. **Lambda Has Permissions**:
   Check the Lambda execution role in AWS Console to verify DynamoDB permissions

3. **Environment Variables Set**:
   ```bash
   aws lambda get-function-configuration --function-name coffee-discovery-mcp
   ```
   
   Verify `DYNAMODB_CART_TABLE` is set to `coffee-cart`

4. **MCP Server Responds**:
   Test the MCP server endpoint:
   ```bash
   curl -X POST <MCP_SERVER_URL> \
     -H "Content-Type: application/json" \
     -d '{"method": "tools/list"}'
   ```
   
   Verify the response includes the 5 new cart tools

### Step 4: Test Cart Functionality

Test the cart tools through ChatGPT:

1. **Add to Cart**:
   - "Add Ethiopian Yirgacheffe to my cart"
   - Verify cart widget displays with the product

2. **View Cart**:
   - "Show me my cart"
   - Verify all items are displayed correctly

3. **Update Quantity**:
   - "Change the quantity of Ethiopian Yirgacheffe to 2"
   - Verify quantity and totals update

4. **Remove Item**:
   - "Remove Ethiopian Yirgacheffe from my cart"
   - Verify item is removed

5. **Clear Cart**:
   - "Clear my cart"
   - Verify empty cart message is displayed

## Rollback Plan

If issues occur, rollback to the previous version:

```bash
cdk deploy --rollback
```

Or manually:
1. Delete the DynamoDB table (if needed)
2. Redeploy the previous Lambda version
3. Remove DynamoDB permissions from the role

## Monitoring

After deployment, monitor:

1. **Lambda Logs**:
   ```bash
   aws logs tail /aws/lambda/coffee-discovery-mcp --follow
   ```

2. **DynamoDB Metrics**:
   - Read/Write capacity units
   - Throttled requests
   - Item count

3. **API Gateway Metrics**:
   - Request count
   - Error rate
   - Latency

## Cost Considerations

The shopping cart feature adds minimal cost:

- **DynamoDB**: Pay-per-request pricing
  - $1.25 per million write requests
  - $0.25 per million read requests
  - $0.25 per GB-month storage
  
- **Lambda**: No additional cost (same function, more code)

Expected monthly cost for moderate usage (1000 users, 10 cart operations each):
- DynamoDB: ~$0.02/month
- Storage: ~$0.01/month
- **Total**: ~$0.03/month

## Troubleshooting

### Issue: DynamoDB Table Already Exists

If the table already exists from a previous deployment:

```bash
aws dynamodb delete-table --table-name coffee-cart
cdk deploy
```

### Issue: Lambda Timeout

If cart operations timeout:
1. Check Lambda timeout setting (currently 60 seconds)
2. Check DynamoDB response times
3. Consider increasing Lambda memory (currently 1024 MB)

### Issue: Permission Denied

If Lambda can't access DynamoDB:
1. Verify IAM role has correct permissions
2. Check resource-based policies
3. Verify table name matches environment variable

## Next Steps

After successful deployment:

1. Load test the cart functionality
2. Monitor error rates and performance
3. Gather user feedback
4. Consider adding:
   - Cart expiration (TTL)
   - Cart sharing
   - Saved carts
   - Checkout integration

## Support

For issues or questions:
- Check CloudWatch Logs for Lambda errors
- Review DynamoDB metrics for throttling
- Check API Gateway logs for request failures

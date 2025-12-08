# Implementation Plan

- [x] 1. Set up DynamoDB infrastructure and cart repository
  - Add DynamoDB table to CDK stack with user_id partition key, TTL attribute
  - Grant Lambda read/write permissions to cart table
  - Add DYNAMODB_CART_TABLE environment variable to Lambda
  - Create cart_repository.py with get_cart, save_cart, delete_cart methods
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 1.1 Write property test for cart persistence
  - **Property 12: Cart modifications persist to DynamoDB**
  - **Validates: Requirements 6.1, 6.3**

- [x] 1.2 Write property test for cart retrieval
  - **Property 13: Cart retrieval loads persisted state**
  - **Validates: Requirements 6.2**

- [x] 1.3 Write property test for empty cart initialization
  - **Property 14: Non-existent carts initialize as empty**
  - **Validates: Requirements 6.4**

- [x] 1.4 Write property test for persisted cart schema
  - **Property 15: Persisted carts contain all required fields**
  - **Validates: Requirements 6.5**

- [x] 2. Implement cart manager business logic
  - Create cart_manager.py with CartManager class
  - Implement add_to_cart method with product validation
  - Implement get_cart method with product enrichment from OpenSearch
  - Implement update_quantity method (0 removes item)
  - Implement remove_item method
  - Implement clear_cart method
  - Implement _enrich_cart_items helper to fetch product details
  - Implement _calculate_totals helper for aggregations
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 4.1, 4.3, 5.1_

- [x] 2.1 Write property test for adding new products
  - **Property 1: Adding new products creates cart items with correct quantity**
  - **Validates: Requirements 1.1, 1.3**

- [x] 2.2 Write property test for adding existing products
  - **Property 2: Adding existing products increments quantity**
  - **Validates: Requirements 1.2**

- [x] 2.3 Write property test for invalid product rejection
  - **Property 4: Invalid product IDs are rejected**
  - **Validates: Requirements 1.5, 9.2**

- [x] 2.4 Write property test for cart totals calculation
  - **Property 5: Cart totals are calculated correctly**
  - **Validates: Requirements 2.2, 2.3, 2.4**

- [x] 2.5 Write property test for cart view completeness
  - **Property 6: Viewing cart returns all items with complete details**
  - **Validates: Requirements 2.1**

- [x] 2.6 Write property test for quantity updates
  - **Property 7: Updating quantity to positive values changes quantity correctly**
  - **Validates: Requirements 3.1**

- [x] 2.7 Write property test for quantity zero removal
  - **Property 8: Updating quantity to zero removes the item**
  - **Validates: Requirements 3.2**

- [x] 2.8 Write property test for non-existent item operations
  - **Property 9: Operations on non-existent items return errors**
  - **Validates: Requirements 3.3, 4.3**

- [x] 2.9 Write property test for item removal
  - **Property 10: Removing items deletes them from cart**
  - **Validates: Requirements 4.1**

- [x] 2.10 Write property test for cart clearing
  - **Property 11: Clearing cart removes all items**
  - **Validates: Requirements 5.1, 5.2**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Create MCP cart tools
  - Create cart_tools.py with tool implementations
  - Implement add_to_cart_tool with user_id extraction from Mcp-Session-Id
  - Implement view_cart_tool
  - Implement update_cart_quantity_tool
  - Implement remove_from_cart_tool
  - Implement clear_cart_tool
  - Add openai/outputTemplate annotations pointing to cart web component
  - Implement error handling with user-friendly messages
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.5, 3.1, 3.2, 3.3, 4.1, 4.3, 5.1, 5.2, 9.1, 9.2, 9.3, 9.4_

- [x] 4.1 Write property test for response format
  - **Property 3: Cart operations return correctly formatted responses**
  - **Validates: Requirements 1.4, 3.4, 4.4, 7.1**

- [x] 4.2 Write property test for input validation
  - **Property 16: Invalid inputs are rejected with descriptive errors**
  - **Validates: Requirements 9.3**

- [x] 4.3 Write property test for infrastructure error handling
  - **Property 17: Infrastructure failures return user-friendly errors**
  - **Validates: Requirements 9.1, 9.4**

- [x] 5. Register cart tools and web component in MCP server
  - Update mcp_server/server.py to import cart tools
  - Register all five cart tools with FastMCP
  - Create cart_component.html web component
  - Register cart web component as MCP resource with uri://widget/cart.html
  - _Requirements: 7.1_

- [x] 6. Implement cart web component UI
  - Create cart_component.html with product grid layout
  - Display cart items with images, names, quantities, prices, subtotals
  - Display total item count and total price
  - Implement empty state message
  - Add window.openai.widgetState management for expanded items
  - Implement toggleItemExpanded function for UI state
  - Implement render function that applies UI state to data
  - Style component to match existing coffee discovery aesthetic
  - _Requirements: 7.2, 7.3, 7.4, 7.5, 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 6.1 Write unit tests for web component (manual browser testing)
  - Test cart display with multiple items
  - Test empty cart display
  - Test widget state persistence for expanded items
  - Test widget state restoration on return to message
  - Test UI state re-application after data updates
  - _Requirements: 7.2, 7.3, 7.4, 8.1, 8.2, 8.3_

- [x] 7. Deploy infrastructure updates
  - Run CDK diff to review changes
  - Deploy CDK stack with new DynamoDB table
  - Verify Lambda has permissions to access cart table
  - Verify environment variables are set correctly
  - Test MCP server endpoint responds to cart tool calls
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

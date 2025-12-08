# Shopping Cart Feature Design

## Overview

This design document specifies the architecture and implementation details for adding shopping cart functionality to the Coffee Discovery ChatGPT application. The shopping cart feature enables users to collect coffee products, manage quantities, view cart contents, and persist their selections across conversation sessions.

The design follows the ChatGPT Apps SDK state management best practices by maintaining authoritative cart data on the server (MCP/DynamoDB) while using ephemeral widget state for UI-only interactions. This ensures data consistency, enables cross-session persistence, and provides a smooth user experience.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        ChatGPT UI                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Cart Web Component (cart_component.html)              │ │
│  │  - Displays cart items with images, quantities, prices │ │
│  │  - Manages ephemeral UI state (expanded items)         │ │
│  │  - Calls MCP tools via window.openai.callTool()        │ │
│  │  - Uses window.openai.widgetState for UI state         │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTPS (MCP Protocol)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              AWS Lambda (MCP Server)                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  FastMCP Server (server.py)                            │ │
│  │  - Registers cart tools and web component              │ │
│  │  - Routes requests to cart_tools.py                    │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Cart Tools (cart_tools.py)                            │ │
│  │  - add_to_cart_tool()                                  │ │
│  │  - view_cart_tool()                                    │ │
│  │  - update_cart_quantity_tool()                         │ │
│  │  - remove_from_cart_tool()                             │ │
│  │  - clear_cart_tool()                                   │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Cart Manager (cart_manager.py)                        │ │
│  │  - Business logic for cart operations                  │ │
│  │  - Validates product IDs against OpenSearch           │ │
│  │  - Calculates totals and formats responses            │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Cart Repository (cart_repository.py)                  │ │
│  │  - DynamoDB CRUD operations                            │ │
│  │  - Manages cart persistence                            │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
    ┌──────────────────┐    ┌──────────────────┐
    │   DynamoDB       │    │   OpenSearch     │
    │   (Cart Data)    │    │   (Products)     │
    │                  │    │                  │
    │  - user_id (PK)  │    │  - Product info  │
    │  - items[]       │    │  - Validation    │
    │  - updated_at    │    │                  │
    └──────────────────┘    └──────────────────┘
```

### State Management Strategy

Following ChatGPT Apps SDK best practices, state is managed in three layers:

1. **Authoritative Business Data (Server-side)**
   - Cart contents (items, quantities, product IDs)
   - Stored in DynamoDB
   - Source of truth for all cart data
   - Persists across sessions and conversations
   - Always returned in tool responses as complete snapshots

2. **Ephemeral UI State (Widget-side)**
   - Expanded/collapsed item details
   - Selected items for bulk operations
   - Scroll position
   - Managed via `window.openai.widgetState`
   - Persists only within the widget instance
   - Re-applied when authoritative data updates

3. **No localStorage Usage**
   - Per SDK guidelines, localStorage is not used for core state
   - All persistent data flows through the server

### User Identification

The system uses the Mcp-Session-Id header provided by ChatGPT as the user identifier for cart operations. This session ID is:
- Automatically provided by the ChatGPT Apps SDK
- Consistent across a user's conversation
- Used as the partition key in DynamoDB
- Enables cart persistence without OAuth (for demo/development)

For production deployments with OAuth enabled, the system can be extended to use authenticated user IDs instead.

## Components and Interfaces

### 1. Cart Repository (cart_repository.py)

**Purpose:** Data access layer for DynamoDB operations

**Interface:**
```python
class CartRepository:
    def __init__(self, table_name: str = "coffee-cart", region: str = "us-east-1")
    
    def get_cart(self, user_id: str) -> Optional[Dict]
        """Retrieve cart for user, returns None if not found"""
    
    def save_cart(self, user_id: str, items: List[Dict], updated_at: str) -> None
        """Save or update cart for user"""
    
    def delete_cart(self, user_id: str) -> None
        """Delete cart for user"""
```

**DynamoDB Schema:**
```python
{
    "user_id": str,        # Partition key (Mcp-Session-Id)
    "items": [             # List of cart items
        {
            "product_id": str,
            "quantity": int,
            "added_at": str  # ISO 8601 timestamp
        }
    ],
    "updated_at": str,     # ISO 8601 timestamp
    "ttl": int             # Optional: Unix timestamp for auto-cleanup
}
```

### 2. Cart Manager (cart_manager.py)

**Purpose:** Business logic layer for cart operations

**Interface:**
```python
class CartManager:
    def __init__(self, cart_repo: CartRepository, opensearch_client: OpenSearchClient)
    
    def add_to_cart(self, user_id: str, product_id: str, quantity: int = 1) -> Dict
        """Add product to cart, returns formatted cart response"""
    
    def get_cart(self, user_id: str) -> Dict
        """Get cart with enriched product details"""
    
    def update_quantity(self, user_id: str, product_id: str, quantity: int) -> Dict
        """Update item quantity (0 removes item)"""
    
    def remove_item(self, user_id: str, product_id: str) -> Dict
        """Remove item from cart"""
    
    def clear_cart(self, user_id: str) -> Dict
        """Remove all items from cart"""
    
    def _enrich_cart_items(self, items: List[Dict]) -> List[Dict]
        """Fetch product details from OpenSearch and merge with cart items"""
    
    def _calculate_totals(self, enriched_items: List[Dict]) -> Dict
        """Calculate item count and total price"""
```

**Cart Response Format:**
```python
{
    "items": [
        {
            "product_id": str,
            "quantity": int,
            "name": str,              # From OpenSearch
            "description": str,       # From OpenSearch
            "origin": str,            # From OpenSearch
            "roast_level": str,       # From OpenSearch
            "flavor_profile": List[str],  # From OpenSearch
            "price": float,           # From OpenSearch
            "image_url": str,         # From OpenSearch
            "subtotal": float         # Calculated: price * quantity
        }
    ],
    "total_items": int,               # Sum of all quantities
    "total_price": float,             # Sum of all subtotals
    "message": str                    # User-friendly message
}
```

### 3. Cart Tools (cart_tools.py)

**Purpose:** MCP tool implementations that expose cart operations to ChatGPT

**Tools:**

```python
@mcp.tool(annotations={"openai/outputTemplate": "ui://widget/cart.html"})
def add_to_cart_tool(product_id: str, quantity: int = 1) -> Dict:
    """
    Add a coffee product to the shopping cart.
    
    Args:
        product_id: Unique product identifier (e.g., "ethiopian-yirgacheffe-light")
        quantity: Number of items to add (default: 1)
    
    Returns:
        Dictionary with updated cart contents and message
    """

@mcp.tool(annotations={"openai/outputTemplate": "ui://widget/cart.html"})
def view_cart_tool() -> Dict:
    """
    View current shopping cart contents.
    
    Returns:
        Dictionary with cart items, totals, and message
    """

@mcp.tool(annotations={"openai/outputTemplate": "ui://widget/cart.html"})
def update_cart_quantity_tool(product_id: str, quantity: int) -> Dict:
    """
    Update the quantity of an item in the cart.
    
    Args:
        product_id: Product identifier
        quantity: New quantity (0 to remove item)
    
    Returns:
        Dictionary with updated cart contents and message
    """

@mcp.tool(annotations={"openai/outputTemplate": "ui://widget/cart.html"})
def remove_from_cart_tool(product_id: str) -> Dict:
    """
    Remove an item from the shopping cart.
    
    Args:
        product_id: Product identifier to remove
    
    Returns:
        Dictionary with updated cart contents and message
    """

@mcp.tool(annotations={"openai/outputTemplate": "ui://widget/cart.html"})
def clear_cart_tool() -> Dict:
    """
    Remove all items from the shopping cart.
    
    Returns:
        Dictionary with empty cart and confirmation message
    """
```

**User ID Extraction:**
All tools extract the user_id from the Mcp-Session-Id header provided by the MCP server context.

### 4. Cart Web Component (cart_component.html)

**Purpose:** Interactive UI for displaying cart contents in ChatGPT

**Features:**
- Displays cart items in a grid layout with product images
- Shows quantities, individual prices, and subtotals
- Displays total item count and total price
- Empty state message when cart is empty
- Uses `window.openai.widgetState` for ephemeral UI state (expanded items)
- Renders from `structuredContent.cart` in tool responses

**UI State Management:**
```javascript
// Initialize widget state
const widgetState = window.openai.widgetState || {
    expandedItems: []  // Array of product_ids with expanded details
};

// Update widget state
function toggleItemExpanded(productId) {
    const expanded = widgetState.expandedItems || [];
    const index = expanded.indexOf(productId);
    
    if (index > -1) {
        expanded.splice(index, 1);
    } else {
        expanded.push(productId);
    }
    
    widgetState.expandedItems = expanded;
    window.openai.setWidgetState(widgetState);
    render();
}

// Re-apply UI state when data updates
function render() {
    const cart = window.openai.toolOutput?.cart || { items: [], total_items: 0, total_price: 0 };
    const expanded = widgetState.expandedItems || [];
    
    // Render items, applying expanded state
    cart.items.forEach(item => {
        const isExpanded = expanded.includes(item.product_id);
        // Render with expansion state
    });
}
```

### 5. Infrastructure Updates (coffee_discovery_stack.py)

**Purpose:** CDK stack modifications to add DynamoDB table

**New Resources:**
```python
# DynamoDB table for cart storage
cart_table = dynamodb.Table(
    self,
    "CoffeeCartTable",
    table_name="coffee-cart",
    partition_key=dynamodb.Attribute(
        name="user_id",
        type=dynamodb.AttributeType.STRING
    ),
    billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
    removal_policy=RemovalPolicy.DESTROY,
    time_to_live_attribute="ttl"  # Optional: auto-cleanup old carts
)

# Grant Lambda permissions
cart_table.grant_read_write_data(lambda_role)

# Add environment variable
mcp_function.add_environment("DYNAMODB_CART_TABLE", cart_table.table_name)
```

## Data Models

### Cart Item (In-Memory)
```python
@dataclass
class CartItem:
    product_id: str
    quantity: int
    added_at: str  # ISO 8601 timestamp
```

### Enriched Cart Item (Response)
```python
@dataclass
class EnrichedCartItem:
    product_id: str
    quantity: int
    name: str
    description: str
    origin: str
    roast_level: str
    flavor_profile: List[str]
    price: float
    image_url: str
    subtotal: float
```

### Cart (DynamoDB)
```python
@dataclass
class Cart:
    user_id: str
    items: List[CartItem]
    updated_at: str  # ISO 8601 timestamp
    ttl: Optional[int]  # Unix timestamp for auto-cleanup
```

### Cart Response (Tool Output)
```python
@dataclass
class CartResponse:
    items: List[EnrichedCartItem]
    total_items: int
    total_price: float
    message: str
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Adding new products creates cart items with correct quantity

*For any* valid product ID and positive quantity, when adding the product to an empty cart, the cart should contain exactly one item with that product ID and the specified quantity.

**Validates: Requirements 1.1, 1.3**

### Property 2: Adding existing products increments quantity

*For any* cart containing a product, when adding that same product with quantity Q, the product's quantity in the cart should increase by Q.

**Validates: Requirements 1.2**

### Property 3: Cart operations return correctly formatted responses

*For any* cart operation (add, view, update, remove, clear), the response should contain the fields: items (array), total_items (int), total_price (float), and message (string), with all values correctly calculated.

**Validates: Requirements 1.4, 3.4, 4.4, 7.1**

### Property 4: Invalid product IDs are rejected

*For any* product ID that does not exist in the Product Catalog, attempting to add it to the cart should return an error and leave the cart unchanged.

**Validates: Requirements 1.5, 9.2**

### Property 5: Cart totals are calculated correctly

*For any* cart state, the total_items should equal the sum of all item quantities, the subtotal for each item should equal price × quantity, and the total_price should equal the sum of all subtotals.

**Validates: Requirements 2.2, 2.3, 2.4**

### Property 6: Viewing cart returns all items with complete details

*For any* cart state, viewing the cart should return all items with all required fields: product_id, quantity, name, description, origin, roast_level, flavor_profile, price, image_url, and subtotal.

**Validates: Requirements 2.1**

### Property 7: Updating quantity to positive values changes quantity correctly

*For any* cart containing a product, when updating that product's quantity to a positive integer N, the cart should contain that product with quantity exactly N, and totals should be recalculated correctly.

**Validates: Requirements 3.1**

### Property 8: Updating quantity to zero removes the item

*For any* cart containing a product, when updating that product's quantity to 0, the product should be completely removed from the cart.

**Validates: Requirements 3.2**

### Property 9: Operations on non-existent items return errors

*For any* cart state and any product ID not in the cart, attempting to update or remove that product should return an error and leave the cart unchanged.

**Validates: Requirements 3.3, 4.3**

### Property 10: Removing items deletes them from cart

*For any* cart containing a product, when removing that product, the cart should no longer contain that product, and totals should be recalculated correctly.

**Validates: Requirements 4.1**

### Property 11: Clearing cart removes all items

*For any* cart state, when clearing the cart, the resulting cart should have zero items, total_items should be 0, and total_price should be 0.

**Validates: Requirements 5.1, 5.2**

### Property 12: Cart modifications persist to DynamoDB

*For any* cart modification operation (add, update, remove, clear), immediately querying DynamoDB for that user's cart should return the updated cart state.

**Validates: Requirements 6.1, 6.3**

### Property 13: Cart retrieval loads persisted state

*For any* user identifier with a persisted cart in DynamoDB, retrieving the cart should return the exact cart state that was persisted, with all items, quantities, and totals matching.

**Validates: Requirements 6.2**

### Property 14: Non-existent carts initialize as empty

*For any* user identifier without a persisted cart in DynamoDB, retrieving the cart should return an empty cart with zero items and zero total price.

**Validates: Requirements 6.4**

### Property 15: Persisted carts contain all required fields

*For any* cart persisted to DynamoDB, the stored record should contain user_id, items (with product_id and quantity for each), and updated_at timestamp.

**Validates: Requirements 6.5**

### Property 16: Invalid inputs are rejected with descriptive errors

*For any* invalid input (negative quantities, empty product IDs, malformed data), the Cart System should reject the operation and return a descriptive error message without modifying the cart.

**Validates: Requirements 9.3**

### Property 17: Infrastructure failures return user-friendly errors

*For any* DynamoDB or OpenSearch operation failure, the Cart System should catch the error and return a user-friendly error message (not exposing internal details).

**Validates: Requirements 9.1, 9.4**

## Error Handling

### Error Categories

1. **Validation Errors**
   - Invalid product IDs (not found in OpenSearch)
   - Invalid quantities (negative, non-integer)
   - Empty or malformed input
   - Response: 400-level error with descriptive message

2. **Business Logic Errors**
   - Updating non-existent cart items
   - Removing non-existent items
   - Response: 404-level error with helpful message

3. **Infrastructure Errors**
   - DynamoDB connection failures
   - DynamoDB read/write errors
   - OpenSearch connection failures
   - OpenSearch query errors
   - Response: 500-level error with user-friendly message

4. **Timeout Errors**
   - DynamoDB operation timeouts
   - OpenSearch query timeouts
   - Response: 504 error with retry suggestion

### Error Response Format

All errors follow a consistent format:

```python
{
    "error": True,
    "message": str,  # User-friendly error message
    "cart": {        # Current cart state (if retrievable)
        "items": [],
        "total_items": 0,
        "total_price": 0.0
    }
}
```

### Error Handling Strategy

1. **Fail Fast**: Validate inputs before any state modifications
2. **Atomic Operations**: Use DynamoDB conditional writes to prevent race conditions
3. **Graceful Degradation**: If product enrichment fails, return basic cart data
4. **Detailed Logging**: Log full error details (stack traces, context) for debugging
5. **User-Friendly Messages**: Return helpful messages without exposing internals

### Example Error Messages

- "Product 'invalid-id' not found in catalog"
- "Quantity must be a positive integer"
- "Item 'product-id' is not in your cart"
- "Unable to save cart. Please try again."
- "Service temporarily unavailable. Please try again in a moment."

## Testing Strategy

### Unit Testing

Unit tests will verify specific examples and edge cases:

1. **Cart Manager Tests**
   - Adding first item to empty cart
   - Adding duplicate items increments quantity
   - Updating quantity to zero removes item
   - Removing last item results in empty cart
   - Clearing empty cart returns appropriate message
   - Invalid product IDs are rejected
   - Negative quantities are rejected

2. **Cart Repository Tests**
   - Saving cart to DynamoDB
   - Retrieving existing cart
   - Retrieving non-existent cart returns None
   - Deleting cart removes from DynamoDB
   - DynamoDB errors are propagated

3. **Cart Tools Tests**
   - User ID extraction from Mcp-Session-Id header
   - Tool responses have correct format
   - Error responses have correct format

### Property-Based Testing

Property-based tests will verify universal properties across many randomly generated inputs using **Hypothesis** (Python property-based testing library).

**Configuration:**
- Minimum 100 iterations per property test
- Random seed for reproducibility
- Shrinking enabled to find minimal failing examples

**Test Generators:**

```python
# Generate valid product IDs from OpenSearch
@st.composite
def valid_product_id(draw):
    products = fetch_all_products_from_opensearch()
    return draw(st.sampled_from([p["product_id"] for p in products]))

# Generate invalid product IDs
@st.composite
def invalid_product_id(draw):
    return draw(st.text(min_size=1, max_size=50).filter(
        lambda x: x not in get_valid_product_ids()
    ))

# Generate positive quantities
positive_quantity = st.integers(min_value=1, max_value=100)

# Generate cart items
@st.composite
def cart_item(draw):
    return {
        "product_id": draw(valid_product_id()),
        "quantity": draw(positive_quantity)
    }

# Generate cart states
@st.composite
def cart_state(draw):
    items = draw(st.lists(cart_item(), min_size=0, max_size=20, unique_by=lambda x: x["product_id"]))
    return {"items": items}

# Generate user IDs
user_id = st.text(min_size=10, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))
```

**Property Test Structure:**

Each property test will:
1. Generate random valid inputs using Hypothesis strategies
2. Execute the operation
3. Verify the property holds
4. Clean up test data from DynamoDB

**Property Test Tags:**

Each property-based test will be tagged with a comment referencing the design property:

```python
@given(product_id=valid_product_id(), quantity=positive_quantity)
def test_adding_new_products_creates_correct_items(product_id, quantity):
    """
    **Feature: shopping-cart, Property 1: Adding new products creates cart items with correct quantity**
    """
    # Test implementation
```

### Integration Testing

Integration tests will verify end-to-end flows:

1. **Full Cart Lifecycle**
   - Add multiple products
   - Update quantities
   - Remove items
   - Clear cart
   - Verify persistence across operations

2. **Cross-Session Persistence**
   - Create cart with user_id_1
   - Simulate new session with same user_id_1
   - Verify cart is retrieved correctly

3. **Web Component Integration**
   - Verify tool responses render correctly in web component
   - Test widget state management (manual browser testing)

### Test Environment

- **Local Testing**: Use DynamoDB Local for unit and property tests
- **Integration Testing**: Use actual AWS DynamoDB in test account
- **Cleanup**: All tests clean up their data after execution
- **Isolation**: Each test uses unique user IDs to prevent interference

## Implementation Notes

### Performance Considerations

1. **DynamoDB Optimization**
   - Use BatchGetItem for enriching multiple products
   - Consider caching product details in cart items (trade-off: stale data vs. performance)
   - Use conditional writes to prevent race conditions

2. **OpenSearch Optimization**
   - Batch product lookups when enriching cart items
   - Cache product details in memory during request lifecycle
   - Consider adding product price/name to cart items to reduce lookups

3. **Lambda Cold Starts**
   - Keep cart operations lightweight
   - Lazy-load OpenSearch client
   - Reuse DynamoDB client across invocations

### Security Considerations

1. **User Isolation**
   - Always use Mcp-Session-Id as user identifier
   - Never allow cross-user cart access
   - Validate user_id format to prevent injection

2. **Input Validation**
   - Sanitize all user inputs
   - Validate product IDs against OpenSearch
   - Enforce quantity limits (e.g., max 100 per item)

3. **Rate Limiting**
   - API Gateway throttling already in place
   - Consider per-user rate limits for cart operations

### Scalability Considerations

1. **DynamoDB Capacity**
   - On-demand billing mode handles variable load
   - Consider provisioned capacity for predictable workloads
   - Monitor for hot partitions (unlikely with user_id as partition key)

2. **Cart Size Limits**
   - Enforce maximum items per cart (e.g., 50 items)
   - DynamoDB item size limit: 400 KB (sufficient for cart data)

3. **TTL for Cleanup**
   - Set TTL to auto-delete carts after 90 days of inactivity
   - Reduces storage costs and cleans up abandoned carts

### Future Enhancements

1. **Checkout Integration**
   - Add checkout tool that processes cart
   - Integration with payment provider
   - Order history tracking

2. **Cart Sharing**
   - Generate shareable cart links
   - Allow users to import shared carts

3. **Saved Carts**
   - Allow users to save multiple named carts
   - "Favorites" or "Wish List" functionality

4. **Inventory Management**
   - Check product availability before adding
   - Reserve inventory during checkout
   - Handle out-of-stock scenarios

5. **Recommendations**
   - "Frequently bought together" suggestions
   - Personalized recommendations based on cart contents

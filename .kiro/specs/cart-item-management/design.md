# Cart Item Management Feature Design

## Overview

This design document specifies the implementation details for adding interactive item management controls to the Shopping Cart GUI. The feature enables users to change item quantities and delete items directly from the cart web component using visual controls, without requiring conversational commands.

The implementation extends the existing cart_component.html to include quantity controls (+/- buttons) and delete buttons for each cart item. These controls invoke the existing MCP tools (update_cart_quantity_tool and remove_from_cart_tool) via the ChatGPT Apps SDK's window.openai.callTool() method.

## Architecture

### Component Interaction Flow

```
┌─────────────────────────────────────────────────────────────┐
│                   Cart Web Component                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Cart Item Row                                         │ │
│  │  ┌─────┐ ┌──────────────┐ ┌───┬───┬───┐ ┌──────────┐  │ │
│  │  │ IMG │ │ Product Info │ │ - │ Q │ + │ │ 🗑 Remove │  │ │
│  │  └─────┘ └──────────────┘ └───┴───┴───┘ └──────────┘  │ │
│  └────────────────────────────────────────────────────────┘ │
│                            │                                 │
│                            ▼                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Event Handlers                                        │ │
│  │  - handleIncrement(productId, currentQty)              │ │
│  │  - handleDecrement(productId, currentQty)              │ │
│  │  - handleDelete(productId)                             │ │
│  └────────────────────────────────────────────────────────┘ │
│                            │                                 │
│                            ▼                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  window.openai.callTool()                              │ │
│  │  - update_cart_quantity_tool(product_id, quantity)     │ │
│  │  - remove_from_cart_tool(product_id)                   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ MCP Protocol
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              MCP Server (Existing)                           │
│  - update_cart_quantity_tool                                 │
│  - remove_from_cart_tool                                     │
│  - Returns updated cart data                                 │
└─────────────────────────────────────────────────────────────┘
```

### State Management

The feature uses the existing state management patterns:

1. **Authoritative Cart Data**: Stored on server (DynamoDB), returned by MCP tools
2. **Loading State**: Managed locally in the web component during async operations
3. **Ephemeral UI State**: Existing widgetState for expanded items (unchanged)

## Components and Interfaces

### 1. Quantity Controls Component

**Purpose:** Allow users to increment/decrement item quantities

**HTML Structure:**
```html
<div class="quantity-controls">
    <button class="qty-btn decrement" onclick="handleDecrement('${productId}', ${quantity})" 
            ${loading ? 'disabled' : ''}>−</button>
    <span class="quantity-value">${quantity}</span>
    <button class="qty-btn increment" onclick="handleIncrement('${productId}', ${quantity})"
            ${loading ? 'disabled' : ''}>+</button>
</div>
```

**Behavior:**
- Increment button: Calls `update_cart_quantity_tool` with `quantity + 1`
- Decrement button (qty > 1): Calls `update_cart_quantity_tool` with `quantity - 1`
- Decrement button (qty = 1): Calls `remove_from_cart_tool` to remove item entirely

### 2. Delete Button Component

**Purpose:** Allow users to remove items entirely from cart

**HTML Structure:**
```html
<button class="delete-btn" onclick="handleDelete('${productId}')"
        ${loading ? 'disabled' : ''}>
    🗑 Remove
</button>
```

**Behavior:**
- Calls `remove_from_cart_tool` with the product_id
- Removes entire item regardless of quantity

### 3. Event Handlers

**handleIncrement(productId, currentQty):**
```javascript
async function handleIncrement(productId, currentQty) {
    setItemLoading(productId, true);
    try {
        const result = await window.openai.callTool('update_cart_quantity_tool', {
            product_id: productId,
            quantity: currentQty + 1
        });
        updateCartData(result);
    } catch (error) {
        showError(productId, 'Failed to update quantity');
    } finally {
        setItemLoading(productId, false);
    }
}
```

**handleDecrement(productId, currentQty):**
```javascript
async function handleDecrement(productId, currentQty) {
    setItemLoading(productId, true);
    try {
        if (currentQty <= 1) {
            // Remove item entirely when quantity would become 0
            const result = await window.openai.callTool('remove_from_cart_tool', {
                product_id: productId
            });
            updateCartData(result);
        } else {
            const result = await window.openai.callTool('update_cart_quantity_tool', {
                product_id: productId,
                quantity: currentQty - 1
            });
            updateCartData(result);
        }
    } catch (error) {
        showError(productId, 'Failed to update quantity');
    } finally {
        setItemLoading(productId, false);
    }
}
```

**handleDelete(productId):**
```javascript
async function handleDelete(productId) {
    setItemLoading(productId, true);
    try {
        const result = await window.openai.callTool('remove_from_cart_tool', {
            product_id: productId
        });
        updateCartData(result);
    } catch (error) {
        showError(productId, 'Failed to remove item');
    } finally {
        setItemLoading(productId, false);
    }
}
```

### 4. Loading State Management

**State Structure:**
```javascript
let loadingItems = new Set(); // Set of product_ids currently loading

function setItemLoading(productId, isLoading) {
    if (isLoading) {
        loadingItems.add(productId);
    } else {
        loadingItems.delete(productId);
    }
    renderCart(); // Re-render to show loading state
}

function isItemLoading(productId) {
    return loadingItems.has(productId);
}
```

### 5. Error Display

**Error State:**
```javascript
let itemErrors = new Map(); // Map of product_id -> error message

function showError(productId, message) {
    itemErrors.set(productId, message);
    renderCart();
    // Auto-clear error after 3 seconds
    setTimeout(() => {
        itemErrors.delete(productId);
        renderCart();
    }, 3000);
}
```

## Data Models

### Cart Item (Extended for UI State)

```javascript
{
    product_id: string,
    quantity: number,
    name: string,
    description: string,
    origin: string,
    roast_level: string,
    flavor_profile: string[],
    price: number,
    image_url: string,
    subtotal: number,
    // UI state (not persisted)
    isLoading: boolean,  // Derived from loadingItems Set
    error: string | null // Derived from itemErrors Map
}
```

### Tool Call Parameters

**update_cart_quantity_tool:**
```javascript
{
    product_id: string,  // Product identifier
    quantity: number     // New quantity (positive integer)
}
```

**remove_from_cart_tool:**
```javascript
{
    product_id: string   // Product identifier to remove
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Controls rendering for cart items

*For any* cart containing items, the rendered HTML for each item should include quantity controls (increment and decrement buttons) and a delete button.

**Validates: Requirements 1.1, 2.1**

### Property 2: Increment calls update with correct quantity

*For any* cart item with quantity Q, clicking the increment button should call update_cart_quantity_tool with quantity = Q + 1.

**Validates: Requirements 1.2**

### Property 3: Decrement calls update with correct quantity

*For any* cart item with quantity Q > 1, clicking the decrement button should call update_cart_quantity_tool with quantity = Q - 1.

**Validates: Requirements 1.3**

### Property 4: Delete calls remove with correct product_id

*For any* cart item, clicking the delete button should call remove_from_cart_tool with the item's product_id, removing the entire item regardless of quantity.

**Validates: Requirements 2.2, 2.3**

### Property 5: UI refresh after successful operation

*For any* successful cart operation (increment, decrement, or delete), the cart display should refresh to show the updated cart data returned by the tool.

**Validates: Requirements 1.5, 2.4**

### Property 6: Loading state lifecycle

*For any* cart operation, the affected item should show a loading state and have controls disabled during the operation, and the loading state should be removed after the operation completes (success or failure).

**Validates: Requirements 3.1, 3.2, 3.3**

### Property 7: Error handling restores state

*For any* failed cart operation, an error message should be displayed for the affected item and the cart should remain in its previous state.

**Validates: Requirements 3.4**

## Error Handling

### Error Categories

1. **Network Errors**
   - Tool call fails due to network issues
   - Response: Show error message, keep previous cart state

2. **Server Errors**
   - MCP tool returns error response
   - Response: Show error message from server, keep previous cart state

3. **Invalid State Errors**
   - Attempting to operate on item that no longer exists
   - Response: Refresh cart data to sync with server state

### Error Display Strategy

- Errors are shown inline on the affected item
- Error messages auto-dismiss after 3 seconds
- User can retry the operation immediately after error clears
- Cart data is not modified on error (optimistic updates not used)

## Testing Strategy

### Unit Testing

Unit tests will verify specific examples and edge cases:

1. **Rendering Tests**
   - Cart item renders with quantity controls
   - Cart item renders with delete button
   - Empty cart does not render controls
   - Loading state disables controls
   - Error state displays message

2. **Event Handler Tests**
   - handleIncrement calls correct tool with correct params
   - handleDecrement calls correct tool when qty > 1
   - handleDecrement calls remove tool when qty = 1
   - handleDelete calls remove tool with correct product_id

3. **State Management Tests**
   - setItemLoading adds/removes from loadingItems
   - showError sets and auto-clears error
   - updateCartData refreshes display

### Property-Based Testing

Property-based tests will verify universal properties across many randomly generated inputs using **Hypothesis** (Python property-based testing library) for backend logic and **fast-check** (JavaScript) for frontend logic if needed.

**Configuration:**
- Minimum 100 iterations per property test
- Random seed for reproducibility

**Test Generators:**

```python
# Generate valid cart items
@st.composite
def cart_item(draw):
    return {
        "product_id": draw(st.text(min_size=5, max_size=30, alphabet=string.ascii_lowercase + "-")),
        "quantity": draw(st.integers(min_value=1, max_value=100)),
        "name": draw(st.text(min_size=1, max_size=50)),
        "price": draw(st.floats(min_value=0.01, max_value=100.0, allow_nan=False)),
        "subtotal": 0.0  # Calculated
    }

# Generate cart states
@st.composite
def cart_state(draw):
    items = draw(st.lists(cart_item(), min_size=0, max_size=10))
    # Ensure unique product_ids
    seen = set()
    unique_items = []
    for item in items:
        if item["product_id"] not in seen:
            seen.add(item["product_id"])
            item["subtotal"] = item["price"] * item["quantity"]
            unique_items.append(item)
    return {"items": unique_items}
```

**Property Test Tags:**

Each property-based test will be tagged with a comment referencing the design property:

```python
@given(cart=cart_state())
def test_controls_rendered_for_all_items(cart):
    """
    **Feature: cart-item-management, Property 1: Controls rendering for cart items**
    """
    # Test implementation
```

### Integration Testing

Integration tests will verify end-to-end flows:

1. **Increment Flow**
   - Click increment on item
   - Verify tool called with correct params
   - Verify UI updates with new quantity

2. **Decrement Flow**
   - Click decrement on item with qty > 1
   - Verify tool called with correct params
   - Verify UI updates with new quantity

3. **Decrement to Remove Flow**
   - Click decrement on item with qty = 1
   - Verify remove tool called
   - Verify item removed from UI

4. **Delete Flow**
   - Click delete on item
   - Verify remove tool called
   - Verify item removed from UI

5. **Error Recovery Flow**
   - Simulate tool failure
   - Verify error displayed
   - Verify cart state unchanged

## Implementation Notes

### CSS Styling

The controls should match the existing cart aesthetic:

```css
.quantity-controls {
    display: flex;
    align-items: center;
    gap: 8px;
}

.qty-btn {
    width: 28px;
    height: 28px;
    border: 1px solid #ddd;
    border-radius: 4px;
    background: white;
    cursor: pointer;
    font-size: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.qty-btn:hover:not(:disabled) {
    background: #f0f0f0;
    border-color: #ccc;
}

.qty-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.delete-btn {
    padding: 6px 12px;
    border: 1px solid #e74c3c;
    border-radius: 4px;
    background: white;
    color: #e74c3c;
    cursor: pointer;
    font-size: 13px;
}

.delete-btn:hover:not(:disabled) {
    background: #e74c3c;
    color: white;
}

.delete-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.item-loading {
    opacity: 0.6;
    pointer-events: none;
}

.item-error {
    color: #e74c3c;
    font-size: 12px;
    margin-top: 4px;
}
```

### Accessibility Considerations

- Buttons have appropriate aria-labels
- Disabled state is communicated to screen readers
- Loading state announced via aria-live region
- Sufficient color contrast for all states

# Add to Cart Button Feature Design

## Overview

This design document specifies the implementation details for adding "Add to Cart" buttons to the Coffee Discovery ChatGPT application. The feature enhances the existing product display web component to include interactive buttons that allow users to add products directly to their shopping cart from both the product list view (search results) and the product details view.

The implementation leverages the existing `add_to_cart_tool` MCP tool and integrates seamlessly with the current shopping cart infrastructure. The buttons will provide visual feedback for loading, success, and error states to ensure a smooth user experience.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        ChatGPT UI                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Product Web Component (web_component.html)            │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │  Product Card (List View)                        │  │ │
│  │  │  - Product image, name, details                  │  │ │
│  │  │  - [Add to Cart] button  ◄── NEW                 │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │  Product Details (Single Product View)           │  │ │
│  │  │  - Full product information                      │  │ │
│  │  │  - [Add to Cart] button  ◄── NEW                 │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ window.openai.callTool()
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              AWS Lambda (MCP Server)                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  add_to_cart_tool (existing)                           │ │
│  │  - Adds product to cart with quantity                  │ │
│  │  - Returns updated cart state                          │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────────┐
│   User      │     │  Web Component  │     │  MCP Server      │
│             │     │                 │     │                  │
└──────┬──────┘     └────────┬────────┘     └────────┬─────────┘
       │                     │                       │
       │  Click "Add to Cart"│                       │
       │────────────────────>│                       │
       │                     │                       │
       │                     │  Show loading state   │
       │                     │──────────┐            │
       │                     │          │            │
       │                     │<─────────┘            │
       │                     │                       │
       │                     │  callTool('add_to_cart_tool')
       │                     │──────────────────────>│
       │                     │                       │
       │                     │                       │  Add to DynamoDB
       │                     │                       │──────────┐
       │                     │                       │          │
       │                     │                       │<─────────┘
       │                     │                       │
       │                     │  Return success/error │
       │                     │<──────────────────────│
       │                     │                       │
       │                     │  Show success/error   │
       │                     │──────────┐            │
       │                     │          │            │
       │                     │<─────────┘            │
       │                     │                       │
       │  See feedback       │                       │
       │<────────────────────│                       │
       │                     │                       │
```

## Components and Interfaces

### 1. Updated Product Web Component (web_component.html)

**Purpose:** Enhanced product display with "Add to Cart" functionality

**New Functions:**

```javascript
/**
 * Handle Add to Cart button click
 * @param {Event} event - Click event
 * @param {Object} product - Product object with product_id
 */
async function handleAddToCart(event, product) {
    // Stop event propagation to prevent card click
    event.stopPropagation();
    
    const button = event.currentTarget;
    const productId = product.product_id;
    
    // Set loading state
    setButtonState(button, 'loading');
    
    try {
        // Call add_to_cart_tool via MCP
        const response = await window.openai.callTool('add_to_cart_tool', {
            product_id: productId,
            quantity: 1
        });
        
        // Show success state
        setButtonState(button, 'success');
        
        // Reset to default after delay
        setTimeout(() => {
            setButtonState(button, 'default');
        }, 2000);
        
    } catch (error) {
        console.error('[Coffee Discovery] Add to cart error:', error);
        setButtonState(button, 'error', error.message || 'Failed to add to cart');
        
        // Reset to default after delay to allow retry
        setTimeout(() => {
            setButtonState(button, 'default');
        }, 3000);
    }
}

/**
 * Set button visual state
 * @param {HTMLElement} button - Button element
 * @param {string} state - 'default' | 'loading' | 'success' | 'error'
 * @param {string} errorMessage - Optional error message
 */
function setButtonState(button, state, errorMessage = '') {
    // Remove all state classes
    button.classList.remove('loading', 'success', 'error');
    
    switch (state) {
        case 'loading':
            button.classList.add('loading');
            button.textContent = 'Adding...';
            button.disabled = true;
            break;
        case 'success':
            button.classList.add('success');
            button.textContent = 'Added! ✓';
            button.disabled = false;
            break;
        case 'error':
            button.classList.add('error');
            button.textContent = 'Try Again';
            button.disabled = false;
            // Show error tooltip/message
            showButtonError(button, errorMessage);
            break;
        default:
            button.textContent = 'Add to Cart';
            button.disabled = false;
            hideButtonError(button);
    }
}

/**
 * Show error message near button
 * @param {HTMLElement} button - Button element
 * @param {string} message - Error message
 */
function showButtonError(button, message) {
    // Find or create error element
    let errorEl = button.parentElement.querySelector('.add-to-cart-error');
    if (!errorEl) {
        errorEl = document.createElement('div');
        errorEl.className = 'add-to-cart-error';
        button.parentElement.appendChild(errorEl);
    }
    errorEl.textContent = message;
    errorEl.style.display = 'block';
}

/**
 * Hide error message
 * @param {HTMLElement} button - Button element
 */
function hideButtonError(button) {
    const errorEl = button.parentElement.querySelector('.add-to-cart-error');
    if (errorEl) {
        errorEl.style.display = 'none';
    }
}
```

**Updated createProductCard Function:**

```javascript
function createProductCard(product) {
    const flavorTags = (product.flavor_profile || [])
        .map(flavor => `<span class="flavor-tag">${escapeHtml(flavor)}</span>`)
        .join('');
    
    return `
        <div class="product-card" data-product-id="${escapeHtml(product.product_id)}">
            <img 
                class="product-image" 
                src="${escapeHtml(product.image_url)}" 
                alt="${escapeHtml(product.name)}"
                onerror="this.src='...placeholder...'"
            />
            <div class="product-content">
                <div class="product-name">${escapeHtml(product.name)}</div>
                <div class="product-origin">${escapeHtml(product.origin)}</div>
                <div class="product-details">
                    <span class="detail-badge roast">${escapeHtml(product.roast_level)} roast</span>
                </div>
                <div class="flavor-profiles">
                    ${flavorTags}
                </div>
                <div class="product-footer">
                    <div class="product-price">$${product.price.toFixed(2)}</div>
                    <button class="add-to-cart-btn" data-product-id="${escapeHtml(product.product_id)}">
                        Add to Cart
                    </button>
                </div>
            </div>
        </div>
    `;
}
```

### 2. CSS Styles for Add to Cart Button

**New Styles:**

```css
/* Add to Cart Button Base Styles */
.add-to-cart-btn {
    background: #10a37f;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    min-width: 110px;
}

.add-to-cart-btn:hover {
    background: #0d8a6a;
    transform: translateY(-1px);
}

.add-to-cart-btn:active {
    transform: translateY(0);
}

/* Loading State */
.add-to-cart-btn.loading {
    background: #6b6b6b;
    cursor: wait;
}

/* Success State */
.add-to-cart-btn.success {
    background: #2e7d32;
}

/* Error State */
.add-to-cart-btn.error {
    background: #c33;
}

/* Error Message */
.add-to-cart-error {
    font-size: 11px;
    color: #c33;
    margin-top: 4px;
    display: none;
}

/* Product Footer Layout */
.product-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 12px;
}

/* Disabled State */
.add-to-cart-btn:disabled {
    cursor: not-allowed;
    opacity: 0.7;
}
```

## Data Models

### Button State

```typescript
type ButtonState = 'default' | 'loading' | 'success' | 'error';

interface AddToCartButtonProps {
    productId: string;
    state: ButtonState;
    errorMessage?: string;
}
```

### Tool Call Parameters

```typescript
interface AddToCartToolParams {
    product_id: string;
    quantity: number;  // Always 1 for button clicks
}
```

### Tool Response (Existing)

```typescript
interface AddToCartResponse {
    items: CartItem[];
    total_items: number;
    total_price: number;
    message: string;
    error?: boolean;
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Add to Cart button renders on each product card

*For any* list of products rendered in the product grid, each product card should contain exactly one "Add to Cart" button element with the correct product_id in its data attribute.

**Validates: Requirements 1.1**

### Property 2: Button click triggers add_to_cart_tool with correct parameters

*For any* product displayed in the web component, when the "Add to Cart" button is clicked, the add_to_cart_tool should be called with that product's product_id and quantity equal to 1.

**Validates: Requirements 1.2, 2.2**

### Property 3: Success feedback is displayed after successful add

*For any* successful add_to_cart_tool response, the button should transition to a success state showing "Added!" text.

**Validates: Requirements 1.3, 2.3, 4.1**

### Property 4: Error message is displayed when tool returns error

*For any* error response from add_to_cart_tool, an error message should be displayed near the button and the button should show an error state.

**Validates: Requirements 1.4, 2.4, 4.3**

### Property 5: Button click does not trigger product card navigation

*For any* "Add to Cart" button click, the event should not propagate to the parent product card's click handler (which navigates to product details).

**Validates: Requirements 3.4**

### Property 6: Button remains functional for retry after error

*For any* error state, after the error display timeout, the button should return to its default state and be clickable again to retry the add operation.

**Validates: Requirements 4.4**

## Error Handling

### Error Categories

1. **Tool Call Errors**
   - Network failures when calling add_to_cart_tool
   - MCP server unavailable
   - Response: Show error message, allow retry

2. **Business Logic Errors**
   - Invalid product ID (product not found)
   - Cart operation failed
   - Response: Show specific error message from tool response

3. **UI Errors**
   - Button element not found
   - Event handler failures
   - Response: Log error, fail gracefully

### Error Response Handling

```javascript
try {
    const response = await window.openai.callTool('add_to_cart_tool', params);
    
    if (response.error) {
        // Business logic error from tool
        setButtonState(button, 'error', response.message);
    } else {
        // Success
        setButtonState(button, 'success');
    }
} catch (error) {
    // Network/system error
    setButtonState(button, 'error', 'Unable to add to cart. Please try again.');
}
```

## Testing Strategy

### Unit Testing

Unit tests will verify specific examples and edge cases:

1. **Button Rendering Tests**
   - Button renders on product cards in list view
   - Button renders on single product in details view
   - Button has correct data-product-id attribute
   - Button has correct initial text "Add to Cart"

2. **Event Handler Tests**
   - Click event calls handleAddToCart function
   - Event propagation is stopped
   - Button state changes to loading on click

3. **State Management Tests**
   - setButtonState correctly applies CSS classes
   - setButtonState correctly updates button text
   - Error message shows/hides correctly

### Property-Based Testing

Property-based tests will verify universal properties across many randomly generated inputs using **Hypothesis** (Python property-based testing library) for backend tests and **fast-check** (JavaScript) for frontend tests if applicable.

**Configuration:**
- Minimum 100 iterations per property test
- Random seed for reproducibility

**Test Approach:**

Since this feature is primarily frontend (HTML/JavaScript), property-based testing will focus on:

1. **Integration tests** that verify the button correctly calls the existing add_to_cart_tool
2. **Backend tests** that verify the add_to_cart_tool handles button-initiated requests correctly (already covered by shopping-cart spec)

**Property Test Tags:**

Each property-based test will be tagged with a comment referencing the design property:

```python
def test_add_to_cart_button_triggers_correct_tool_call():
    """
    **Feature: add-to-cart-button, Property 2: Button click triggers add_to_cart_tool with correct parameters**
    """
    # Test implementation
```

### Manual Testing

Due to the UI-centric nature of this feature, manual testing in the ChatGPT environment will verify:

1. Button appears on all product cards
2. Button click shows loading state
3. Success state shows "Added!" briefly
4. Error state shows error message
5. Button click does not navigate to product details
6. Retry works after error

## Implementation Notes

### Event Propagation

The "Add to Cart" button is nested inside a clickable product card. To prevent the card's click handler (which navigates to product details) from firing when the button is clicked:

```javascript
function handleAddToCart(event, product) {
    event.stopPropagation();  // Critical: prevent card click
    // ... rest of handler
}
```

### Button Attachment

After rendering product cards, event listeners must be attached to the buttons:

```javascript
function attachAddToCartHandlers() {
    const buttons = document.querySelectorAll('.add-to-cart-btn');
    buttons.forEach(button => {
        const productId = button.dataset.productId;
        const product = currentProducts.find(p => p.product_id === productId);
        if (product) {
            button.addEventListener('click', (e) => handleAddToCart(e, product));
        }
    });
}
```

### Accessibility Considerations

1. **Button Semantics**: Use `<button>` element for proper keyboard accessibility
2. **ARIA Labels**: Add aria-label for screen readers
3. **Focus States**: Ensure visible focus indicator
4. **Color Contrast**: Use WCAG AA compliant colors

### Performance Considerations

1. **Debouncing**: Prevent rapid multiple clicks
2. **Optimistic UI**: Consider showing success immediately (optional enhancement)
3. **Minimal DOM Updates**: Only update the clicked button, not entire grid


# Cart Component Manual Testing Guide

This document describes the manual browser tests that should be performed for the cart web component.

## Test 1: Cart Display with Multiple Items

**Steps:**
1. Add multiple products to the cart using the `add_to_cart` tool
2. Call `view_cart` tool to display the cart
3. Verify the cart component renders correctly

**Expected Results:**
- All cart items are displayed with:
  - Product image
  - Product name
  - Origin and roast level
  - Price per item
  - Quantity
  - Subtotal
- Total item count is correct
- Total price is correct
- Items are displayed in a clean grid layout

## Test 2: Empty Cart Display

**Steps:**
1. Call `view_cart` tool on an empty cart (or after calling `clear_cart`)
2. Verify the empty state is displayed

**Expected Results:**
- Empty cart icon (🛒) is displayed
- "Your cart is empty" message is shown
- No cart items are rendered
- Total shows 0 items and $0.00

## Test 3: Widget State Persistence for Expanded Items

**Steps:**
1. Add multiple products to cart
2. View cart and expand one or more items by clicking on the product name
3. Scroll away from the cart widget
4. Return to the same cart widget message

**Expected Results:**
- Expanded items remain expanded when returning to the widget
- Collapsed items remain collapsed
- Widget state is persisted using `window.openai.widgetState`

## Test 4: Widget State Restoration on Return to Message

**Steps:**
1. Add products to cart and expand some items
2. Navigate to a different message in the conversation
3. Return to the cart widget message

**Expected Results:**
- The widget restores the exact same expansion state
- No items change their expanded/collapsed state unexpectedly

## Test 5: UI State Re-application After Data Updates

**Steps:**
1. View cart with multiple items
2. Expand some items
3. Update cart (add item, remove item, or update quantity)
4. Verify the new cart is displayed

**Expected Results:**
- Cart data is updated with new items/quantities/totals
- Previously expanded items remain expanded if they still exist in the cart
- New items are collapsed by default
- Removed items are no longer shown
- Widget state is correctly re-applied to the new data

## Test 6: Error Display

**Steps:**
1. Trigger an error (e.g., try to add an invalid product)
2. Verify error message is displayed

**Expected Results:**
- Error message is shown in a red error box
- Error message is user-friendly
- Cart state is still displayed (if available)

## Test 7: Expand/Collapse Interaction

**Steps:**
1. View cart with items
2. Click on a product name to expand it
3. Verify additional details are shown
4. Click again to collapse

**Expected Results:**
- Clicking expands the item to show description and flavor profile
- Expand icon changes from ▶ to ▼
- Clicking again collapses the item
- Expand icon changes back to ▶
- Widget state is updated via `window.openai.setWidgetState`

## Notes

- All tests should be performed in the ChatGPT interface where the MCP server is deployed
- Widget state management relies on `window.openai.widgetState` and `window.openai.setWidgetState`
- The component should match the aesthetic of the existing coffee discovery widget

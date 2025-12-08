# Implementation Plan

- [x] 1. Add CSS styles for Add to Cart button
  - Add button base styles (.add-to-cart-btn) with green background, white text, rounded corners
  - Add hover state styles with darker green and subtle lift effect
  - Add loading state styles (.loading) with gray background
  - Add success state styles (.success) with dark green background
  - Add error state styles (.error) with red background
  - Add error message styles (.add-to-cart-error)
  - Add product footer layout styles (.product-footer) for price and button alignment
  - Add disabled state styles
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 2. Update product card HTML template to include Add to Cart button
  - Modify createProductCard function to include product-footer div
  - Move price into product-footer
  - Add Add to Cart button with data-product-id attribute
  - Ensure button is inside product-content but has its own click handler
  - _Requirements: 1.1, 2.1_

- [ ]* 2.1 Write property test for button rendering
  - **Property 1: Add to Cart button renders on each product card**
  - **Validates: Requirements 1.1**

- [x] 3. Implement handleAddToCart function
  - Create handleAddToCart(event, product) function
  - Add event.stopPropagation() to prevent card click
  - Extract product_id from product object
  - Call window.openai.callTool('add_to_cart_tool', {product_id, quantity: 1})
  - Handle success response by setting success state
  - Handle error response by setting error state with message
  - Add try/catch for network errors
  - _Requirements: 1.2, 1.3, 1.4, 2.2, 2.3, 2.4, 3.4_

- [ ]* 3.1 Write property test for tool call parameters
  - **Property 2: Button click triggers add_to_cart_tool with correct parameters**
  - **Validates: Requirements 1.2, 2.2**

- [ ]* 3.2 Write property test for event propagation
  - **Property 5: Button click does not trigger product card navigation**
  - **Validates: Requirements 3.4**

- [x] 4. Implement button state management functions
  - Create setButtonState(button, state, errorMessage) function
  - Implement 'default' state: text "Add to Cart", enabled
  - Implement 'loading' state: text "Adding...", disabled, gray background
  - Implement 'success' state: text "Added! ✓", enabled, green background
  - Implement 'error' state: text "Try Again", enabled, red background
  - Add setTimeout to reset success state after 2 seconds
  - Add setTimeout to reset error state after 3 seconds
  - _Requirements: 1.3, 1.5, 2.3, 2.5, 4.1, 4.2_

- [ ]* 4.1 Write property test for success feedback
  - **Property 3: Success feedback is displayed after successful add**
  - **Validates: Requirements 1.3, 2.3, 4.1**

- [ ]* 4.2 Write property test for error feedback
  - **Property 4: Error message is displayed when tool returns error**
  - **Validates: Requirements 1.4, 2.4, 4.3**

- [x] 5. Implement error message display functions
  - Create showButtonError(button, message) function
  - Create or find error element near button
  - Display error message text
  - Create hideButtonError(button) function
  - Hide error element when state resets
  - _Requirements: 4.3, 4.4_

- [ ]* 5.1 Write property test for retry functionality
  - **Property 6: Button remains functional for retry after error**
  - **Validates: Requirements 4.4**

- [x] 6. Attach event handlers to Add to Cart buttons
  - Create attachAddToCartHandlers() function
  - Query all .add-to-cart-btn elements
  - For each button, find corresponding product from currentProducts
  - Add click event listener calling handleAddToCart
  - Call attachAddToCartHandlers() after renderProducts()
  - _Requirements: 1.2, 2.2_

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Test integration with existing cart functionality
  - Verify button click adds item to cart in DynamoDB
  - Verify cart count updates correctly
  - Verify multiple clicks increment quantity
  - Test error handling when product doesn't exist
  - _Requirements: 1.2, 1.3, 1.4_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.


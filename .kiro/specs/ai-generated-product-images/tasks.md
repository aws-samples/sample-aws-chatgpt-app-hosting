# Implementation Plan

- [ ] 1. Create image generation module
  - Create new Python module for Nova Canvas integration
  - Implement prompt generation from product data
  - Implement image generation with retry logic
  - Implement base64 encoding
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.5_

- [x] 1.1 Create image_generator.py module structure
  - Create `scripts/image_generator.py` file
  - Add imports for boto3, base64, time, logging
  - Define module-level constants (model ID, dimensions, retry config)
  - _Requirements: 1.1_

- [x] 1.2 Implement prompt generation function
  - Create `create_image_prompt(product: dict) -> str` function
  - Include product name, description, origin, roast_level in prompt
  - Add professional photography styling keywords
  - Add studio lighting and white background keywords
  - _Requirements: 1.2, 1.3, 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 1.3 Write property test for prompt generation
  - **Property 1: Prompt completeness**
  - **Property 2: Prompt styling keywords**
  - **Validates: Requirements 1.2, 1.3, 6.1, 6.2, 6.3, 6.4, 6.5**

- [x] 1.4 Implement Nova Canvas API call
  - Create `generate_product_image(product, model_id, width, height, max_retries) -> Optional[bytes]` function
  - Initialize Bedrock runtime client
  - Construct API request with prompt and parameters
  - Call `invoke_model` with Nova Canvas model ID
  - Parse response and extract image bytes
  - _Requirements: 1.1, 1.4_

- [x] 1.5 Implement retry logic with exponential backoff
  - Add retry loop with max_retries parameter
  - Implement exponential backoff (1s, 2s, 4s)
  - Add jitter (±20%) to backoff delays
  - Log each retry attempt with error details
  - Return None if all retries fail
  - _Requirements: 1.5, 5.3_

- [x] 1.6 Implement image validation
  - Create `validate_image(image_bytes: bytes) -> bool` function
  - Check image data is non-empty
  - Check image size is between 10KB and 500KB
  - Verify PNG format signature (optional: use Pillow)
  - Log validation failures
  - _Requirements: 1.4, 8.1, 8.2, 8.4_

- [x] 1.7 Write property test for image validation
  - **Property 3: Image generation produces data**
  - **Property 14: Image size validation**
  - **Validates: Requirements 1.4, 8.1, 8.2**

- [x] 1.8 Implement base64 encoding function
  - Create `encode_image_base64(image_bytes: bytes) -> str` function
  - Use standard base64.b64encode()
  - Decode to UTF-8 string
  - Ensure no line breaks in output
  - _Requirements: 2.1, 2.5_

- [x] 1.9 Write property test for base64 encoding
  - **Property 4: Base64 encoding round-trip**
  - **Property 5: Base64 encoding format**
  - **Validates: Requirements 2.1, 2.5, 8.3**

- [ ] 2. Update load_catalog.py script
  - Add command-line arguments for image generation control
  - Integrate image generation into product loading flow
  - Add progress tracking and logging
  - Handle image generation failures gracefully
  - _Requirements: 2.2, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.4, 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 2.1 Add command-line arguments
  - Add `--skip-images` flag to skip image generation
  - Add `--regenerate-images` flag to force regeneration
  - Add `--image-width` argument (default: 512)
  - Add `--image-height` argument (default: 512)
  - Add `--model-id` argument (default: amazon.nova-canvas-v1:0)
  - _Requirements: 7.1, 7.2, 7.4, 7.5_

- [x] 2.2 Implement image generation integration
  - Import image_generator module
  - Add image generation step before indexing each product
  - Check if --skip-images flag is set
  - Check if product already has image_base64 and --regenerate-images is false
  - Call generate_product_image() for each product
  - Add image_base64 field to product document if generation succeeds
  - Preserve image_url field if generation fails
  - _Requirements: 2.2, 5.2, 7.3_

- [x] 2.3 Write property test for image field handling
  - **Property 7: Image field presence**
  - **Property 12: Fallback preservation**
  - **Property 13: Skip existing images**
  - **Validates: Requirements 2.2, 5.2, 7.3**

- [x] 2.4 Add progress logging
  - Log total number of products at script start
  - Log progress for each product (name, count, total)
  - Log image generation time for each product
  - Log summary statistics at script end (total time, success rate, failures)
  - Log errors with product ID when generation fails
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1_

- [x] 2.5 Write property test for progress logging
  - **Property 15: Progress logging**
  - **Validates: Requirements 4.2, 4.3**

- [x] 2.6 Implement error handling
  - Wrap image generation in try-except block
  - Log API errors with details
  - Continue processing remaining products on error
  - Track failed products for summary report
  - _Requirements: 5.1, 5.4_

- [x] 2.7 Write property test for error continuation
  - **Property 11: Error continuation**
  - **Validates: Requirements 5.4**


- [ ] 3. Update OpenSearch index mapping
  - Add image_base64 field to index mapping
  - Verify mapping is applied correctly
  - _Requirements: 2.3_

- [x] 3.1 Update index creation in load_catalog.py
  - Add image_base64 field to index mapping
  - Set type to "keyword"
  - Set index: false (not searchable)
  - Set doc_values: false (save disk space)
  - _Requirements: 2.3_

- [x] 3.2 Verify document size limits
  - Add document size check before indexing
  - Log warning if document exceeds 1MB
  - Skip image_base64 if document would exceed limits
  - _Requirements: 2.4_

- [x] 3.3 Write property test for document size
  - **Property 6: Document size bounds**
  - **Validates: Requirements 2.4**

- [ ] 4. Update web component for data URI rendering
  - Modify image rendering logic to support data URIs
  - Implement priority: image_base64 over image_url
  - Maintain backward compatibility with image_url
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4.1 Update getImageSource function
  - Check if product has image_base64 field
  - If present, construct data URI: `data:image/png;base64,${image_base64}`
  - If absent, fall back to image_url
  - Return empty string if neither field exists
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4.2 Write property test for data URI construction
  - **Property 8: Data URI construction**
  - **Validates: Requirements 3.1, 3.5**

- [x] 4.3 Write property test for image source priority
  - **Property 9: Image source priority**
  - **Property 10: Fallback behavior**
  - **Validates: Requirements 3.3, 3.4, 5.5**

- [x] 4.4 Test web component rendering
  - Create test products with image_base64
  - Create test products with only image_url
  - Create test products with both fields
  - Verify correct image source is used in each case
  - Verify images render correctly in browser
  - _Requirements: 3.2, 3.3, 3.4_

- [ ] 5. Update documentation
  - Document new command-line arguments
  - Document image generation process
  - Document troubleshooting for image generation failures
  - Update README with Nova Canvas requirements
  - _Requirements: All_

- [x] 5.1 Update README.md
  - Add Nova Canvas to prerequisites section
  - Document Bedrock permissions required (bedrock:InvokeModel)
  - Add section on image generation in "Load Product Catalog" step
  - Document new command-line flags (--skip-images, --regenerate-images, etc.)
  - Add troubleshooting section for image generation failures
  - Document image storage approach (base64 in OpenSearch)
  - _Requirements: All_

- [x] 5.2 Update load_catalog.py help text
  - Add detailed help text for each new command-line argument
  - Include examples of common usage patterns
  - Document default values
  - _Requirements: 7.1, 7.2, 7.4, 7.5_

- [ ] 6. Test end-to-end flow
  - Run load script with image generation
  - Verify images stored in OpenSearch
  - Query products via MCP tools
  - Verify web component displays images correctly
  - Test error scenarios
  - _Requirements: All_

- [x] 6.1 Test successful image generation
  - Run load_catalog.py with default settings
  - Verify all products get image_base64 field
  - Check OpenSearch documents contain base64 data
  - Verify images display in web component
  - _Requirements: 1.1, 2.2, 3.1, 3.2_

- [x] 6.2 Test skip images flag
  - Run load_catalog.py with --skip-images
  - Verify no image generation occurs
  - Verify products use image_url fallback
  - _Requirements: 7.1_

- [x] 6.3 Test regenerate images flag
  - Run load_catalog.py twice
  - First run: generates images
  - Second run without --regenerate-images: skips existing
  - Second run with --regenerate-images: regenerates all
  - _Requirements: 7.2, 7.3_

- [x] 6.4 Test error handling
  - Simulate Nova Canvas API failure (mock or invalid credentials)
  - Verify script continues processing
  - Verify failed products preserve image_url
  - Verify error logging works correctly
  - _Requirements: 5.1, 5.2, 5.4_

- [x] 6.5 Test image dimensions configuration
  - Run load_catalog.py with --image-width 1024 --image-height 1024
  - Verify generated images have correct dimensions
  - _Requirements: 7.4_

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

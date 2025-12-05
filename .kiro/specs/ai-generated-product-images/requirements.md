# Requirements Document

## Introduction

This feature enhances the Coffee Discovery application by replacing external stock photos with AI-generated product images. Using Amazon Bedrock's Nova Canvas model, the system will generate realistic coffee bag photographs with product-specific branding and store them as base64-encoded data directly in OpenSearch, eliminating the need for additional storage infrastructure.

## Glossary

- **Nova Canvas**: Amazon Bedrock's image generation model
- **Base64 Encoding**: Binary-to-text encoding scheme for embedding images in data
- **Data URI**: URL scheme that embeds data inline using base64 encoding
- **OpenSearch**: The search and analytics engine storing product catalog
- **Product Catalog**: JSON file containing coffee product definitions
- **Load Script**: Python script that indexes products into OpenSearch
- **Web Component**: HTML/JavaScript UI component displaying products in ChatGPT

## Requirements

### Requirement 1

**User Story:** As a coffee retailer, I want AI-generated product images that display the product name on each coffee bag, so that customers see branded, professional product photography.

#### Acceptance Criteria

1. WHEN the load script processes a product THEN the system SHALL generate an image using Nova Canvas with the product name visible on the coffee bag
2. WHEN generating an image THEN the system SHALL include the product description in the prompt to influence visual style
3. WHEN generating an image THEN the system SHALL use professional product photography styling with studio lighting and clean background
4. WHEN an image is generated THEN the system SHALL validate that the image data is non-empty and properly formatted
5. WHEN image generation fails THEN the system SHALL retry up to 3 times with exponential backoff

### Requirement 2

**User Story:** As a system administrator, I want images stored directly in OpenSearch as base64 data, so that I avoid managing additional AWS storage resources.

#### Acceptance Criteria

1. WHEN an image is generated THEN the system SHALL convert the image bytes to base64 encoding
2. WHEN storing a product THEN the system SHALL add an image_base64 field to the OpenSearch document
3. WHEN the OpenSearch index is created THEN the system SHALL include mapping for the image_base64 field as keyword type
4. WHEN a product document is indexed THEN the system SHALL verify the total document size remains under OpenSearch limits
5. WHEN base64 encoding is performed THEN the system SHALL use standard base64 encoding without line breaks

### Requirement 3

**User Story:** As a developer, I want the web component to display AI-generated images using data URIs, so that images load directly from product data without external requests.

#### Acceptance Criteria

1. WHEN the web component receives product data with image_base64 THEN the system SHALL construct a data URI with proper MIME type
2. WHEN rendering a product tile THEN the system SHALL use the data URI as the image source
3. WHEN image_base64 is present THEN the system SHALL prefer it over image_url
4. WHEN image_base64 is absent THEN the system SHALL fall back to image_url for backward compatibility
5. WHEN constructing data URIs THEN the system SHALL use image/png as the MIME type

### Requirement 4

**User Story:** As a system administrator, I want the load script to generate images efficiently with progress tracking, so that I can monitor the catalog loading process.

#### Acceptance Criteria

1. WHEN the load script starts THEN the system SHALL log the total number of products to process
2. WHEN generating each image THEN the system SHALL log progress with product name and current count
3. WHEN an image generation completes THEN the system SHALL log the generation time
4. WHEN all products are processed THEN the system SHALL log summary statistics including total time and success rate
5. WHEN image generation fails after retries THEN the system SHALL log the error and continue processing remaining products

### Requirement 5

**User Story:** As a developer, I want proper error handling for image generation failures, so that the system degrades gracefully when Nova Canvas is unavailable.

#### Acceptance Criteria

1. WHEN Nova Canvas API returns an error THEN the system SHALL log the error details
2. WHEN image generation fails after all retries THEN the system SHALL preserve the existing image_url field
3. WHEN Bedrock throttles requests THEN the system SHALL implement exponential backoff with jitter
4. WHEN the load script encounters an error THEN the system SHALL continue processing remaining products
5. WHEN a product has no image_base64 after loading THEN the web component SHALL display the image_url fallback

### Requirement 6

**User Story:** As a coffee retailer, I want image generation prompts to reflect coffee characteristics, so that generated images match the product's roast level and origin.

#### Acceptance Criteria

1. WHEN generating a prompt THEN the system SHALL include the product name as the primary label text
2. WHEN generating a prompt THEN the system SHALL include roast level to influence bag color and style
3. WHEN generating a prompt THEN the system SHALL include origin country for cultural design elements
4. WHEN generating a prompt THEN the system SHALL specify professional product photography style
5. WHEN generating a prompt THEN the system SHALL request studio lighting and clean white background

### Requirement 7

**User Story:** As a system administrator, I want to control image generation behavior through configuration, so that I can adjust quality and performance settings.

#### Acceptance Criteria

1. WHEN the load script runs THEN the system SHALL support a command-line flag to skip image generation
2. WHEN the load script runs THEN the system SHALL support a command-line flag to regenerate all images
3. WHEN regenerate flag is false THEN the system SHALL skip products that already have image_base64
4. WHEN the load script runs THEN the system SHALL use configurable image dimensions (default 512x512)
5. WHEN the load script runs THEN the system SHALL use configurable Nova Canvas model ID

### Requirement 8

**User Story:** As a developer, I want the system to validate generated images, so that only valid images are stored in OpenSearch.

#### Acceptance Criteria

1. WHEN an image is generated THEN the system SHALL verify the response contains image data
2. WHEN an image is generated THEN the system SHALL verify the image size is within expected bounds (10KB-500KB)
3. WHEN an image is generated THEN the system SHALL verify the base64 encoding is valid
4. WHEN validation fails THEN the system SHALL log the validation error and retry generation
5. WHEN validation fails after all retries THEN the system SHALL skip storing image_base64 for that product

# Requirements Document

## Introduction

This feature tests S3 + CloudFront infrastructure for hosting product images by uploading a single test image. The goal is to validate that images can be stored in S3, served through CloudFront CDN, and displayed correctly in the ChatGPT web component without CORS or CSP errors. This is a proof-of-concept before migrating all product images.

## Glossary

- **S3 (Simple Storage Service)**: AWS object storage service for storing product images
- **CloudFront**: AWS Content Delivery Network (CDN) for fast global image delivery
- **OAI (Origin Access Identity)**: CloudFront feature that restricts S3 bucket access to only CloudFront
- **CORS (Cross-Origin Resource Sharing)**: HTTP headers that allow web components to load images from different domains
- **CSP (Content Security Policy)**: MCP server metadata that controls which domains can load resources in ChatGPT
- **Web Component**: HTML/JavaScript UI component displaying products in ChatGPT iframe

## Requirements

### Requirement 1: Infrastructure Setup

**User Story:** As a developer, I want S3 and CloudFront infrastructure deployed, so that I can host a single test image.

#### Acceptance Criteria

1. WHEN the CDK stack deploys THEN the system SHALL create an S3 bucket named "chatgpt-apps-aws"
2. WHEN the CloudFront distribution is created THEN the system SHALL configure Origin Access Identity (OAI)
3. WHEN the S3 bucket is created THEN the system SHALL configure CORS to allow GET requests from any origin
4. WHEN the infrastructure is deployed THEN the system SHALL output the CloudFront distribution domain name

### Requirement 2: CSP Configuration

**User Story:** As a developer, I want CSP configured in the MCP server, so that images load in ChatGPT without CSP violations.

#### Acceptance Criteria

1. WHEN MCP tools return results THEN the system SHALL include openai/widgetCSP metadata
2. WHEN widgetCSP is configured THEN the system SHALL add CloudFront domain to resource_domains
3. WHEN the Lambda function is deployed THEN the system SHALL set CLOUDFRONT_DOMAIN environment variable

### Requirement 3: Generate and Upload Test Image

**User Story:** As a developer, I want to generate a single AI image and upload it to S3, so that I can test the complete pipeline with Nova Canvas.

#### Acceptance Criteria

1. WHEN the test script runs THEN the system SHALL generate an image using Nova Canvas for the first product
2. WHEN uploading the image THEN the system SHALL upload to S3 with key: images/{product_id}.png
3. WHEN the upload completes THEN the system SHALL output the CloudFront URL

### Requirement 4: Verify Image Access

**User Story:** As a developer, I want to verify the image loads in ChatGPT, so that I know the complete pipeline works.

#### Acceptance Criteria

1. WHEN testing with curl THEN the system SHALL return HTTP 200 for the CloudFront URL
2. WHEN accessing the image THEN the system SHALL include proper CORS headers
3. WHEN loading in ChatGPT THEN the system SHALL display the image without CSP violations

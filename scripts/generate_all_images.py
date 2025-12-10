#!/usr/bin/env python3
"""
Generate AI images for all products and upload to S3/CloudFront.

This script:
1. Reads all products from data/products.json
2. Generates an image using Nova Canvas for each product
3. Uploads each image to S3
4. Updates products.json with CloudFront URLs
5. Reloads the catalog to OpenSearch

Reuses existing scripts:
- scripts/image_generator.py for image generation
- scripts/upload_to_s3.py for S3 upload
"""

import json
import sys
import os
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
import time

# Set AWS region before importing boto3-dependent modules
if not os.environ.get('AWS_REGION') and not os.environ.get('AWS_DEFAULT_REGION'):
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.image_generator import generate_product_image
from scripts.upload_to_s3 import upload_image_to_s3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_cloudfront_domain():
    """Get CloudFront domain from CDK outputs."""
    import boto3
    
    try:
        cfn = boto3.client('cloudformation', region_name='us-east-1')
        response = cfn.describe_stacks(StackName='ImageHostingStack')
        outputs = response['Stacks'][0]['Outputs']
        
        for output in outputs:
            if output['OutputKey'] == 'ProductImagesCDNDomain':
                domain = output['OutputValue']
                return domain.replace('https://', '').replace('http://', '')
    except Exception as e:
        logger.error(f"Could not get CloudFront domain from CDK: {e}")
        return None


def get_bucket_name():
    """Get S3 bucket name from CDK outputs or construct from account ID."""
    import boto3
    
    try:
        cfn = boto3.client('cloudformation', region_name='us-east-1')
        response = cfn.describe_stacks(StackName='ImageHostingStack')
        outputs = response['Stacks'][0]['Outputs']
        
        for output in outputs:
            if output['OutputKey'] == 'ProductImagesBucketName':
                return output['OutputValue']
    except Exception:
        pass
    
    # Fallback: construct from account ID
    try:
        sts = boto3.client('sts', region_name='us-east-1')
        account_id = sts.get_caller_identity()['Account']
        return f"chatgpt-apps-aws-{account_id}"
    except Exception as e:
        logger.error(f"Could not determine bucket name: {e}")
        return None


def generate_all_images(skip_existing=True, delay_seconds=2):
    """
    Generate images for all products and upload to CloudFront.
    
    Args:
        skip_existing: If True, skip products that already have CloudFront URLs
        delay_seconds: Delay between image generations to avoid rate limits
    """
    PRODUCTS_FILE = Path("data/products.json")
    
    logger.info("=" * 70)
    logger.info("Generating AI Images for All Products")
    logger.info("=" * 70)
    
    # Get CloudFront domain and bucket name
    cloudfront_domain = get_cloudfront_domain()
    bucket_name = get_bucket_name()
    
    if not cloudfront_domain or not bucket_name:
        logger.error("Could not determine CloudFront domain or S3 bucket name")
        logger.error("Please ensure ImageHostingStack is deployed")
        sys.exit(1)
    
    logger.info(f"CloudFront domain: {cloudfront_domain}")
    logger.info(f"S3 bucket: {bucket_name}")
    
    # Load products
    logger.info(f"\nLoading products from {PRODUCTS_FILE}")
    with open(PRODUCTS_FILE) as f:
        data = json.load(f)
    
    products = data.get('products', [])
    logger.info(f"Found {len(products)} products")
    
    # Filter products if skipping existing
    if skip_existing:
        products_to_process = [
            p for p in products 
            if not p.get('image_url', '').startswith(f'https://{cloudfront_domain}')
        ]
        logger.info(f"Skipping {len(products) - len(products_to_process)} products with CloudFront URLs")
        logger.info(f"Processing {len(products_to_process)} products")
    else:
        products_to_process = products
    
    if not products_to_process:
        logger.info("\nAll products already have CloudFront URLs!")
        return
    
    # Process each product
    success_count = 0
    error_count = 0
    
    for i, product in enumerate(products_to_process, 1):
        product_id = product['product_id']
        product_name = product['name']
        
        logger.info(f"\n[{i}/{len(products_to_process)}] Processing: {product_name}")
        logger.info(f"  Product ID: {product_id}")
        
        try:
            # Generate image
            logger.info(f"  Generating image with Nova Canvas...")
            image_bytes = generate_product_image(
                product=product,
                use_webp=False,  # Use PNG for compatibility
                max_retries=3
            )
            
            if not image_bytes:
                logger.error(f"  ✗ Failed to generate image")
                error_count += 1
                continue
            
            logger.info(f"  ✓ Image generated ({len(image_bytes)} bytes)")
            
            # Save to temporary file
            with NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                tmp_file.write(image_bytes)
                tmp_path = tmp_file.name
            
            try:
                # Upload to S3
                logger.info(f"  Uploading to S3...")
                cloudfront_url = upload_image_to_s3(
                    image_source=tmp_path,
                    product_id=product_id,
                    bucket_name=bucket_name,
                    cloudfront_domain=cloudfront_domain
                )
                
                logger.info(f"  ✓ Uploaded: {cloudfront_url}")
                
                # Update product in data
                product['image_url'] = cloudfront_url
                success_count += 1
                
            finally:
                # Clean up temporary file
                Path(tmp_path).unlink(missing_ok=True)
            
            # Delay between generations to avoid rate limits
            if i < len(products_to_process):
                logger.info(f"  Waiting {delay_seconds}s before next generation...")
                time.sleep(delay_seconds)
        
        except Exception as e:
            logger.error(f"  ✗ Error processing {product_name}: {e}")
            error_count += 1
            continue
    
    # Save updated products.json
    logger.info(f"\n{'=' * 70}")
    logger.info(f"Saving updated products.json...")
    with open(PRODUCTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"✓ Updated {PRODUCTS_FILE}")
    
    # Print summary
    logger.info(f"\n{'=' * 70}")
    logger.info(f"Summary:")
    logger.info(f"  Total processed: {len(products_to_process)}")
    logger.info(f"  Successful: {success_count}")
    logger.info(f"  Failed: {error_count}")
    logger.info(f"{'=' * 70}")
    
    if success_count > 0:
        logger.info(f"\nNext steps:")
        logger.info(f"  1. Run: python3 scripts/load_catalog.py")
        logger.info(f"  2. Test in ChatGPT to verify images load correctly")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate AI images for all products using Nova Canvas'
    )
    parser.add_argument(
        '--regenerate-all',
        action='store_true',
        help='Regenerate images even for products with CloudFront URLs'
    )
    parser.add_argument(
        '--delay',
        type=int,
        default=2,
        help='Delay in seconds between image generations (default: 2)'
    )
    
    args = parser.parse_args()
    
    try:
        generate_all_images(
            skip_existing=not args.regenerate_all,
            delay_seconds=args.delay
        )
        logger.info(f"\n✓ Image generation completed!")
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("\n\nImage generation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n✗ Image generation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

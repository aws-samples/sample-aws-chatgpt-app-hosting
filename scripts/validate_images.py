#!/usr/bin/env python3
"""
Validation script to check if Nova Canvas generated images are in OpenSearch.

This script queries OpenSearch and checks:
1. How many products have image_base64 field
2. Sample sizes of image_base64 data
3. Whether image_base64 data looks like valid base64-encoded images
"""
import os
import sys
import json
import base64
import logging
from pathlib import Path

# Add mcp_server to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'mcp_server'))

from opensearch_client import OpenSearchClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_base64_image(base64_str: str) -> dict:
    """
    Validate that a base64 string represents a valid PNG image.
    
    Returns:
        Dictionary with validation results
    """
    try:
        # Decode base64
        image_bytes = base64.b64decode(base64_str)
        
        # Check PNG signature
        png_signature = b'\x89PNG\r\n\x1a\n'
        is_png = image_bytes.startswith(png_signature)
        
        return {
            "valid": True,
            "is_png": is_png,
            "size_bytes": len(image_bytes),
            "base64_length": len(base64_str)
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }


def main():
    """Main validation logic"""
    try:
        # Initialize OpenSearch client
        logger.info("Connecting to OpenSearch...")
        client = OpenSearchClient()
        
        # Query all products
        logger.info("Querying all products...")
        query = {
            "size": 100,  # Get all products
            "query": {
                "match_all": {}
            }
        }
        
        response = client.client.search(index=client.index_name, body=query)
        products = [hit["_source"] for hit in response["hits"]["hits"]]
        
        logger.info(f"Found {len(products)} products in OpenSearch")
        
        # Analyze products
        products_with_base64 = []
        products_without_base64 = []
        
        for product in products:
            product_id = product.get("product_id", "unknown")
            name = product.get("name", "Unknown")
            has_base64 = "image_base64" in product and product["image_base64"]
            
            if has_base64:
                products_with_base64.append(product)
            else:
                products_without_base64.append(product)
        
        # Print summary
        print("\n" + "=" * 70)
        print("IMAGE VALIDATION SUMMARY")
        print("=" * 70)
        print(f"Total products: {len(products)}")
        print(f"Products WITH image_base64: {len(products_with_base64)}")
        print(f"Products WITHOUT image_base64: {len(products_without_base64)}")
        print("=" * 70)
        
        # Validate a few samples
        if products_with_base64:
            print("\nValidating sample images...")
            print("-" * 70)
            
            for i, product in enumerate(products_with_base64[:5]):  # Check first 5
                product_id = product.get("product_id", "unknown")
                name = product.get("name", "Unknown")
                image_base64 = product.get("image_base64", "")
                
                validation = validate_base64_image(image_base64)
                
                print(f"\nProduct: {name} ({product_id})")
                print(f"  Base64 length: {validation.get('base64_length', 0):,} chars")
                
                if validation.get("valid"):
                    print(f"  Image size: {validation.get('size_bytes', 0):,} bytes")
                    print(f"  Is PNG: {validation.get('is_png', False)}")
                    print(f"  Status: ✓ VALID")
                else:
                    print(f"  Status: ✗ INVALID - {validation.get('error', 'Unknown error')}")
            
            print("-" * 70)
        
        # List products without images
        if products_without_base64:
            print("\nProducts WITHOUT image_base64:")
            print("-" * 70)
            for product in products_without_base64[:10]:  # Show first 10
                product_id = product.get("product_id", "unknown")
                name = product.get("name", "Unknown")
                image_url = product.get("image_url", "")
                print(f"  - {name} ({product_id})")
                print(f"    Fallback URL: {image_url}")
            
            if len(products_without_base64) > 10:
                print(f"  ... and {len(products_without_base64) - 10} more")
            print("-" * 70)
        
        # Conclusion
        print("\n" + "=" * 70)
        print("CONCLUSION")
        print("=" * 70)
        
        if len(products_with_base64) == len(products):
            print("✓ All products have Nova Canvas generated images!")
        elif len(products_with_base64) > 0:
            print(f"⚠ Only {len(products_with_base64)}/{len(products)} products have generated images.")
            print("  You may need to regenerate images for the remaining products.")
        else:
            print("✗ No products have Nova Canvas generated images!")
            print("  All products are using fallback image_url from Unsplash.")
            print("\nTo generate images, run:")
            print("  python3 scripts/load_catalog.py")
        
        print("=" * 70)
        
    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

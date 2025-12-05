#!/usr/bin/env python3
"""
Test script to check what the MCP server returns for product images.

This simulates calling the MCP tools and inspects the response to see
if image_base64 is included.
"""
import os
import sys
import json
from pathlib import Path

# Add mcp_server to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'mcp_server'))

# Set up environment
os.environ.setdefault('AWS_REGION', 'us-east-1')
os.environ.setdefault('OPENSEARCH_ENDPOINT', 'https://fd8e6kvqc6bzfp19qou1.us-east-1.aoss.amazonaws.com')

from tools import search_products, get_product_details


def main():
    print("=" * 70)
    print("MCP IMAGE RESPONSE TEST")
    print("=" * 70)
    print()
    
    # Test 1: Search for products
    print("Test 1: Searching for products...")
    print("-" * 70)
    
    try:
        response = search_products("fruity light roast")
        
        # Check structuredContent
        structured = response.get('structuredContent', {})
        products = structured.get('products', [])
        
        print(f"Found {len(products)} products")
        print()
        
        if products:
            # Inspect first product
            first_product = products[0]
            print(f"First product: {first_product.get('name', 'Unknown')}")
            print(f"Product ID: {first_product.get('product_id', 'Unknown')}")
            print()
            print("Fields in response:")
            for key in sorted(first_product.keys()):
                value = first_product[key]
                if key == 'image_base64':
                    print(f"  ✓ {key}: {len(value)} chars (BASE64 DATA PRESENT!)")
                elif key == 'image_url':
                    print(f"  - {key}: {value}")
                else:
                    print(f"  - {key}: {value}")
            
            print()
            
            # Check if image_base64 is present
            if 'image_base64' in first_product:
                print("✓ SUCCESS: image_base64 field IS present in response!")
                print(f"  Base64 length: {len(first_product['image_base64'])} characters")
            else:
                print("✗ PROBLEM: image_base64 field is NOT present in response!")
                print("  Only image_url is being returned.")
                print()
                print("This means:")
                print("  1. Either the products in OpenSearch don't have image_base64")
                print("  2. Or the format_product_for_response() function is filtering it out")
        
        print("-" * 70)
        print()
        
        # Test 2: Get specific product details
        if products:
            product_id = products[0].get('product_id')
            print(f"Test 2: Getting details for product {product_id}...")
            print("-" * 70)
            
            details_response = get_product_details(product_id)
            structured = details_response.get('structuredContent', {})
            detail_products = structured.get('products', [])
            
            if detail_products:
                detail_product = detail_products[0]
                print(f"Product: {detail_product.get('name', 'Unknown')}")
                print()
                print("Fields in response:")
                for key in sorted(detail_product.keys()):
                    value = detail_product[key]
                    if key == 'image_base64':
                        print(f"  ✓ {key}: {len(value)} chars (BASE64 DATA PRESENT!)")
                    elif key == 'image_url':
                        print(f"  - {key}: {value}")
                    else:
                        print(f"  - {key}: {value}")
                
                print()
                
                if 'image_base64' in detail_product:
                    print("✓ SUCCESS: image_base64 field IS present in details response!")
                else:
                    print("✗ PROBLEM: image_base64 field is NOT present in details response!")
            
            print("-" * 70)
        
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print()
    print("The issue is in mcp_server/tools.py:")
    print("The format_product_for_response() function only returns these fields:")
    print("  - product_id, name, description, origin, roast_level")
    print("  - flavor_profile, price, image_url")
    print()
    print("It does NOT include image_base64!")
    print()
    print("To fix this, we need to:")
    print("  1. Update format_product_for_response() to include image_base64")
    print("  2. Update the web component to use image_base64 when available")
    print("=" * 70)


if __name__ == "__main__":
    main()

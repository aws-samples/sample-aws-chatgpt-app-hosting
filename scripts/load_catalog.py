#!/usr/bin/env python3
"""
Data loading script for coffee product catalog
Loads products from JSON file into OpenSearch Serverless with embeddings

KNOWN ISSUE: This script sometimes fails with 403 Forbidden errors even when
permissions are correct. This appears to be related to OpenSearch Serverless
policy propagation delays or boto3 session handling in complex scripts.

If this script fails with 403:
1. Wait 2-5 minutes after any policy changes
2. Verify: aws sts get-caller-identity
3. Try the simpler alternative: python3 scripts/simple_load.py

The simple_load.py script uses a minimal approach that often succeeds when
this script encounters permission issues. Both scripts produce the same result.
"""
import argparse
import json
import logging
import sys
import os
from pathlib import Path
from typing import Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description='Load coffee product catalog into OpenSearch Serverless'
    )
    parser.add_argument(
        '--data-file',
        type=str,
        default='data/products.json',
        help='Path to products JSON file (default: data/products.json)'
    )
    parser.add_argument(
        '--opensearch-endpoint',
        type=str,
        help='OpenSearch endpoint URL (defaults to OPENSEARCH_ENDPOINT env var)'
    )
    parser.add_argument(
        '--region',
        type=str,
        help='AWS region (defaults to AWS_REGION env var or us-west-2)'
    )
    parser.add_argument(
        '--index-name',
        type=str,
        default='coffee-products',
        help='OpenSearch index name (default: products)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    # Image generation arguments
    parser.add_argument(
        '--skip-images',
        action='store_true',
        help='Skip AI image generation entirely (use existing image_url values)'
    )
    parser.add_argument(
        '--regenerate-images',
        action='store_true',
        help='Force regeneration of all images (even if image_base64 already exists)'
    )
    parser.add_argument(
        '--image-width',
        type=int,
        default=512,
        help='Generated image width in pixels (default: 512)'
    )
    parser.add_argument(
        '--image-height',
        type=int,
        default=512,
        help='Generated image height in pixels (default: 512)'
    )
    parser.add_argument(
        '--model-id',
        type=str,
        default='amazon.nova-canvas-v1:0',
        help='Bedrock Nova Canvas model ID (default: amazon.nova-canvas-v1:0)'
    )
    
    return parser.parse_args()


def setup_opensearch_client(endpoint: str, region: str):
    """
    Set up OpenSearch client with AWS SigV4 authentication
    
    Args:
        endpoint: OpenSearch endpoint URL
        region: AWS region
    
    Returns:
        OpenSearch client instance
    
    Raises:
        Exception: If connection fails
    """
    from opensearchpy import OpenSearch, RequestsHttpConnection
    from requests_aws4auth import AWS4Auth
    import boto3
    
    try:
        logger.info(f"Connecting to OpenSearch at {endpoint}")
        
        # Set up AWS SigV4 authentication
        credentials = boto3.Session().get_credentials()
        logger.debug(f"Using credentials: access_key={credentials.access_key[:10]}..., has_token={credentials.token is not None}")
        awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            region,
            'aoss',  # OpenSearch Serverless service name
            session_token=credentials.token
        )
        
        # Initialize OpenSearch client
        client = OpenSearch(
            hosts=[{'host': endpoint.replace('https://', ''), 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=30
        )
        
        # Note: OpenSearch Serverless doesn't support the info() API
        # Connection will be verified when we try to use it
        logger.info(f"OpenSearch client configured successfully")
        
        return client
        
    except Exception as e:
        logger.error(f"Failed to connect to OpenSearch: {str(e)}")
        raise


def create_index_if_not_exists(client, index_name: str):
    """
    Create OpenSearch index with appropriate mappings if it doesn't exist
    
    Args:
        client: OpenSearch client
        index_name: Name of the index to create
    
    Raises:
        Exception: If index creation fails
    """
    try:
        # Check if index already exists
        if client.indices.exists(index=index_name):
            logger.info(f"Index '{index_name}' already exists")
            return
        
        logger.info(f"Creating index '{index_name}'")
        
        # Define index mappings for text and vector search
        index_body = {
            "settings": {
                "index": {
                    "knn": True,  # Enable k-NN for vector search
                    "knn.algo_param.ef_search": 512
                }
            },
            "mappings": {
                "properties": {
                    "product_id": {
                        "type": "keyword"
                    },
                    "name": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword"
                            }
                        }
                    },
                    "description": {
                        "type": "text"
                    },
                    "origin": {
                        "type": "keyword"
                    },
                    "roast_level": {
                        "type": "keyword"
                    },
                    "flavor_profile": {
                        "type": "keyword"
                    },
                    "price": {
                        "type": "float"
                    },
                    "image_url": {
                        "type": "keyword"
                    },
                    "image_base64": {
                        "type": "keyword",
                        "index": False,
                        "doc_values": False
                    },
                    "description_embedding": {
                        "type": "knn_vector",
                        "dimension": 1536,  # Titan embeddings dimension
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib",
                            "parameters": {
                                "ef_construction": 512,
                                "m": 16
                            }
                        }
                    }
                }
            }
        }
        
        # Create the index
        response = client.indices.create(index=index_name, body=index_body)
        logger.info(f"Index '{index_name}' created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create index: {str(e)}")
        raise


def load_products_from_file(file_path: str) -> List[Dict]:
    """
    Load products from JSON file
    
    Args:
        file_path: Path to products JSON file
    
    Returns:
        List of product dictionaries
    
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
        ValueError: If products data is invalid
    """
    try:
        logger.info(f"Loading products from {file_path}")
        
        # Check if file exists
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Products file not found: {file_path}")
        
        # Read and parse JSON
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Extract products array
        if 'products' not in data:
            raise ValueError("JSON file must contain 'products' array")
        
        products = data['products']
        
        if not isinstance(products, list):
            raise ValueError("'products' must be an array")
        
        if len(products) == 0:
            raise ValueError("Products array is empty")
        
        logger.info(f"Loaded {len(products)} products from file")
        return products
        
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error loading products: {str(e)}")
        raise


def validate_product(product: Dict, index: int) -> bool:
    """
    Validate that a product has all required fields
    
    Args:
        product: Product dictionary
        index: Product index (for error reporting)
    
    Returns:
        True if valid, False otherwise
    """
    required_fields = [
        'product_id', 'name', 'description', 'origin',
        'roast_level', 'flavor_profile', 'price', 'image_url'
    ]
    
    missing_fields = []
    for field in required_fields:
        if field not in product:
            missing_fields.append(field)
    
    if missing_fields:
        logger.error(
            f"Product at index {index} is missing required fields: {', '.join(missing_fields)}"
        )
        return False
    
    # Validate data types
    if not isinstance(product['product_id'], str) or not product['product_id']:
        logger.error(f"Product at index {index} has invalid product_id")
        return False
    
    if not isinstance(product['flavor_profile'], list):
        logger.error(f"Product at index {index} has invalid flavor_profile (must be array)")
        return False
    
    if not isinstance(product['price'], (int, float)) or product['price'] <= 0:
        logger.error(f"Product at index {index} has invalid price")
        return False
    
    return True


def generate_images_for_products(
    products: List[Dict],
    model_id: str,
    width: int,
    height: int,
    skip_existing: bool = True
) -> tuple[List[Dict], int, int]:
    """
    Generate AI images for products using Nova Canvas
    
    Args:
        products: List of product dictionaries
        model_id: Bedrock Nova Canvas model ID
        width: Image width in pixels
        height: Image height in pixels
        skip_existing: Skip products that already have image_base64
    
    Returns:
        Tuple of (products with images, success_count, failure_count)
    """
    # Import image generator module
    sys.path.insert(0, str(Path(__file__).parent))
    from image_generator import generate_product_image, encode_image_base64
    
    import time
    
    logger.info(f"Generating AI images for products (width={width}, height={height})")
    logger.info(f"Total products to process: {len(products)}")
    
    success_count = 0
    failure_count = 0
    skipped_count = 0
    start_time = time.time()
    
    for i, product in enumerate(products):
        product_id = product.get('product_id', 'unknown')
        product_name = product.get('name', 'Unknown')
        
        # Skip if product already has image_base64 and we're not regenerating
        if skip_existing and 'image_base64' in product and product['image_base64']:
            logger.debug(f"Skipping product {product_id} - already has image_base64")
            skipped_count += 1
            continue
        
        logger.info(f"Generating image for product {i + 1}/{len(products)}: {product_name}")
        
        image_start_time = time.time()
        
        # Generate image
        image_bytes = generate_product_image(
            product=product,
            model_id=model_id,
            width=width,
            height=height
        )
        
        image_duration = time.time() - image_start_time
        
        if image_bytes:
            # Encode to base64
            image_base64 = encode_image_base64(image_bytes)
            product['image_base64'] = image_base64
            success_count += 1
            logger.info(f"Successfully generated image for {product_name} in {image_duration:.2f}s "
                       f"({len(image_bytes)} bytes, {len(image_base64)} base64 chars)")
        else:
            # Generation failed - preserve image_url
            failure_count += 1
            logger.warning(f"Failed to generate image for {product_name} - will use image_url fallback")
    
    total_duration = time.time() - start_time
    
    # Log summary
    logger.info("=" * 60)
    logger.info("Image generation summary:")
    logger.info(f"  Total products: {len(products)}")
    logger.info(f"  Successfully generated: {success_count}")
    logger.info(f"  Failed: {failure_count}")
    logger.info(f"  Skipped (already have images): {skipped_count}")
    logger.info(f"  Total time: {total_duration:.2f}s")
    if success_count > 0:
        logger.info(f"  Average time per image: {total_duration / success_count:.2f}s")
    logger.info("=" * 60)
    
    return products, success_count, failure_count


def generate_embeddings_for_products(products: List[Dict], region: str) -> List[Dict]:
    """
    Generate embeddings for all products using Bedrock
    
    Args:
        products: List of product dictionaries
        region: AWS region
    
    Returns:
        List of products with embeddings added
    
    Raises:
        Exception: If embedding generation fails
    """
    # Add mcp_server to path to import embeddings module
    sys.path.insert(0, str(Path(__file__).parent.parent / 'mcp_server'))
    from embeddings import EmbeddingsGenerator
    
    try:
        logger.info("Initializing embeddings generator")
        embeddings_gen = EmbeddingsGenerator(region=region)
        
        logger.info(f"Generating embeddings for {len(products)} products")
        
        for i, product in enumerate(products):
            # Create embedding text from description and flavor profile
            embedding_text = f"{product['description']} Flavor profile: {', '.join(product['flavor_profile'])}"
            
            logger.debug(f"Generating embedding for product {i + 1}/{len(products)}: {product['product_id']}")
            
            embedding = embeddings_gen.generate_embedding(embedding_text)
            product['description_embedding'] = embedding
            
            if (i + 1) % 5 == 0:
                logger.info(f"Generated embeddings for {i + 1}/{len(products)} products")
        
        logger.info(f"Successfully generated embeddings for all {len(products)} products")
        return products
        
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {str(e)}")
        raise


def index_products(client, index_name: str, products: List[Dict]) -> int:
    """
    Index products into OpenSearch (idempotent using product_id)
    
    Args:
        client: OpenSearch client
        index_name: Name of the index
        products: List of products with embeddings
    
    Returns:
        Number of products successfully indexed
    
    Raises:
        Exception: If indexing fails
    """
    try:
        logger.info(f"Indexing {len(products)} products into '{index_name}'")
        
        indexed_count = 0
        MAX_DOCUMENT_SIZE = 1024 * 1024  # 1MB (well under OpenSearch's 100MB limit)
        
        for i, product in enumerate(products):
            product_id = product['product_id']
            
            # Check document size
            product_json = json.dumps(product)
            document_size = len(product_json.encode('utf-8'))
            
            if document_size > MAX_DOCUMENT_SIZE:
                logger.warning(f"Product {product_id} document size ({document_size} bytes) exceeds 1MB limit")
                # Remove image_base64 to reduce size
                if 'image_base64' in product:
                    logger.warning(f"Removing image_base64 from product {product_id} to reduce document size")
                    del product['image_base64']
                    # Recalculate size
                    product_json = json.dumps(product)
                    document_size = len(product_json.encode('utf-8'))
                    logger.info(f"Product {product_id} size after removing image: {document_size} bytes")
            
            # OpenSearch Serverless doesn't support custom document IDs
            # Just index the document and let OpenSearch generate the ID
            response = client.index(
                index=index_name,
                body=product,
                refresh=False  # Don't refresh after each document
            )
            
            indexed_count += 1
            
            if (i + 1) % 5 == 0:
                logger.info(f"Indexed {i + 1}/{len(products)} products")
        
        # Note: OpenSearch Serverless doesn't support manual refresh
        # Documents will be available for search within a few seconds
        
        logger.info(f"Successfully indexed {indexed_count} products")
        logger.info("Note: Documents will be available for search within a few seconds")
        return indexed_count
        
    except Exception as e:
        logger.error(f"Failed to index products: {str(e)}")
        raise


def main():
    """
    Main entry point
    
    Exit codes:
        0: Success
        1: File not found or configuration error
        2: OpenSearch connection error
        3: Bedrock API error
        4: Data validation error
    """
    args = parse_arguments()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("Starting product catalog loading process")
    logger.info(f"Data file: {args.data_file}")
    
    try:
        # Step 1: Load products from file
        try:
            products = load_products_from_file(args.data_file)
        except FileNotFoundError as e:
            logger.error(f"File not found: {str(e)}")
            logger.error("Please ensure the products JSON file exists at the specified path")
            sys.exit(1)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid data file: {str(e)}")
            logger.error("Please ensure the file contains valid JSON with a 'products' array")
            sys.exit(1)
        
        # Step 2: Validate products
        logger.info("Validating products...")
        invalid_products = []
        valid_products = []
        
        for i, product in enumerate(products):
            if validate_product(product, i):
                valid_products.append(product)
            else:
                invalid_products.append(i)
        
        if invalid_products:
            logger.error(f"Found {len(invalid_products)} invalid products at indices: {invalid_products}")
            logger.error("Please fix the product data and try again")
            sys.exit(4)
        
        logger.info(f"All {len(valid_products)} products are valid")
        
        # Step 3: Generate AI images (if not skipped)
        if args.skip_images:
            logger.info("Skipping AI image generation (--skip-images flag set)")
        else:
            try:
                skip_existing = not args.regenerate_images
                valid_products, img_success, img_failure = generate_images_for_products(
                    products=valid_products,
                    model_id=args.model_id,
                    width=args.image_width,
                    height=args.image_height,
                    skip_existing=skip_existing
                )
                
                if img_failure > 0:
                    logger.warning(f"{img_failure} products failed image generation - they will use image_url fallback")
                    
            except Exception as e:
                logger.error(f"Image generation failed: {str(e)}")
                logger.warning("Continuing with product loading using image_url fallback")
                # Don't exit - continue with loading
        
        # Step 4: Set up OpenSearch connection
        opensearch_endpoint = args.opensearch_endpoint or os.getenv("OPENSEARCH_ENDPOINT")
        if not opensearch_endpoint:
            logger.error("OpenSearch endpoint not provided")
            logger.error("Please set OPENSEARCH_ENDPOINT environment variable or use --opensearch-endpoint")
            sys.exit(1)
        
        region = args.region or os.getenv("AWS_REGION", "us-west-2")
        
        try:
            client = setup_opensearch_client(opensearch_endpoint, region)
        except Exception as e:
            logger.error(f"Failed to connect to OpenSearch: {str(e)}")
            logger.error("Troubleshooting steps:")
            logger.error("  1. Verify the OpenSearch endpoint URL is correct")
            logger.error("  2. Ensure AWS credentials are configured (aws configure)")
            logger.error("  3. Check that your IAM role/user has permissions for OpenSearch Serverless")
            logger.error("  4. Verify the OpenSearch collection exists and is active")
            sys.exit(2)
        
        # Step 5: Skip index creation - index already exists
        logger.info(f"Skipping index creation check - assuming '{args.index_name}' already exists")
        
        # Step 6: Generate embeddings
        try:
            products_with_embeddings = generate_embeddings_for_products(valid_products, region)
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {str(e)}")
            logger.error("Troubleshooting steps:")
            logger.error("  1. Verify AWS credentials are configured")
            logger.error("  2. Check that your IAM role/user has permissions for Bedrock")
            logger.error("  3. Ensure the Bedrock model is available in your region")
            logger.error("  4. Check for API throttling or quota limits")
            sys.exit(3)
        
        # Step 7: Index products
        try:
            # Recreate client right before indexing to ensure fresh credentials
            logger.info("Recreating OpenSearch client for indexing...")
            client = setup_opensearch_client(opensearch_endpoint, region)
            indexed_count = index_products(client, args.index_name, products_with_embeddings)
        except Exception as e:
            logger.error(f"Failed to index products: {str(e)}")
            logger.error("Please check OpenSearch permissions and try again")
            sys.exit(2)
        
        # Success!
        logger.info("=" * 60)
        logger.info("Product catalog loading completed successfully!")
        logger.info(f"  Total products loaded: {indexed_count}")
        logger.info(f"  Index name: {args.index_name}")
        logger.info(f"  OpenSearch endpoint: {opensearch_endpoint}")
        logger.info("=" * 60)
        
        sys.exit(0)
        
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.exception("Full traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
Image generation module for Coffee Discovery application.

This module provides functionality to generate product images using Amazon Bedrock
Nova Canvas and encode them as base64 for storage in OpenSearch.
"""

import base64
import json
import logging
import random
import time
from typing import Optional
from io import BytesIO

import boto3
from botocore.exceptions import ClientError

try:
    from PIL import Image
except ImportError:
    Image = None

# Configure logging
logger = logging.getLogger(__name__)

# Module-level constants
DEFAULT_MODEL_ID = "amazon.nova-canvas-v1:0"
DEFAULT_WIDTH = 320  # Minimum size for Nova Canvas (reduced from 512)
DEFAULT_HEIGHT = 320  # Minimum size for Nova Canvas (reduced from 512)
DEFAULT_MAX_RETRIES = 3

# Retry configuration
INITIAL_BACKOFF = 1.0  # seconds
BACKOFF_MULTIPLIER = 2.0
JITTER_PERCENT = 0.2  # ±20%

# Image validation bounds
MIN_IMAGE_SIZE = 5 * 1024  # 5KB (reduced for smaller images)
MAX_IMAGE_SIZE = 250 * 1024  # 250KB (PNG before WebP compression)



def create_image_prompt(product: dict) -> str:
    """
    Create Nova Canvas prompt from product data.
    
    Generates a detailed prompt that includes the product name, description,
    origin, roast level, and professional photography styling keywords.
    
    Args:
        product: Product dictionary with name, description, origin, roast_level fields
        
    Returns:
        Formatted prompt string for Nova Canvas image generation
    """
    name = product.get("name", "Coffee")
    description = product.get("description", "")
    origin = product.get("origin", "")
    roast_level = product.get("roast_level", "")
    
    # Build the prompt with all required elements
    prompt = (
        f"A professional product photograph of a premium coffee bag labeled '{name}'. "
    )
    
    if roast_level and origin:
        prompt += f"The bag is a {roast_level} roast coffee from {origin}. "
    elif roast_level:
        prompt += f"The bag is a {roast_level} roast coffee. "
    elif origin:
        prompt += f"The bag is coffee from {origin}. "
    
    if description:
        prompt += f"{description} "
    
    prompt += (
        f"The product name '{name}' is prominently displayed on the label. "
        "Studio lighting, white background, commercial product photography style, "
        "high quality, detailed, professional."
    )
    
    return prompt



def convert_png_to_webp(png_bytes: bytes, quality: int = 85) -> bytes:
    """
    Convert PNG image to WebP format for better compression.
    
    Args:
        png_bytes: Raw PNG image data
        quality: WebP quality (0-100, default 85 for good balance)
        
    Returns:
        WebP image bytes
        
    Raises:
        ImportError: If PIL/Pillow is not installed
        Exception: If conversion fails
    """
    if Image is None:
        raise ImportError("Pillow is required for WebP conversion. Install with: pip install Pillow")
    
    try:
        # Open PNG image from bytes
        png_image = Image.open(BytesIO(png_bytes))
        
        # Convert to RGB if necessary (WebP doesn't support all PNG modes)
        if png_image.mode in ('RGBA', 'LA', 'P'):
            # Create white background for transparency
            background = Image.new('RGB', png_image.size, (255, 255, 255))
            if png_image.mode == 'P':
                png_image = png_image.convert('RGBA')
            if 'A' in png_image.mode:
                background.paste(png_image, mask=png_image.split()[-1])
            else:
                background.paste(png_image)
            png_image = background
        elif png_image.mode != 'RGB':
            png_image = png_image.convert('RGB')
        
        # Save as WebP to bytes buffer
        webp_buffer = BytesIO()
        png_image.save(webp_buffer, format='WEBP', quality=quality, method=6)
        webp_bytes = webp_buffer.getvalue()
        
        logger.debug(f"Converted PNG ({len(png_bytes)} bytes) to WebP ({len(webp_bytes)} bytes) - "
                    f"{100 * (1 - len(webp_bytes)/len(png_bytes)):.1f}% reduction")
        
        return webp_bytes
        
    except Exception as e:
        logger.error(f"Failed to convert PNG to WebP: {e}")
        raise


def encode_image_base64(image_bytes: bytes) -> str:
    """
    Encode image bytes as base64 string.
    
    Uses standard base64 encoding without line breaks, suitable for
    embedding in JSON documents and data URIs.
    
    Args:
        image_bytes: Raw image data (PNG or WebP format)
        
    Returns:
        Base64-encoded string without line breaks
    """
    # Encode to base64 and decode to UTF-8 string
    # base64.b64encode returns bytes, we need a string
    encoded = base64.b64encode(image_bytes)
    return encoded.decode('utf-8')



def validate_image(image_bytes: bytes, format_type: str = 'PNG') -> bool:
    """
    Validate generated image data.
    
    Checks that the image data is non-empty, within expected size bounds,
    and has a valid format signature.
    
    Args:
        image_bytes: Raw image data to validate
        format_type: Expected format ('PNG' or 'WEBP')
        
    Returns:
        True if image is valid, False otherwise
    """
    # Check if image data is non-empty
    if not image_bytes:
        logger.warning("Image validation failed: empty image data")
        return False
    
    # Check image size bounds
    image_size = len(image_bytes)
    if image_size < MIN_IMAGE_SIZE:
        logger.warning(f"Image validation failed: size {image_size} bytes is below minimum {MIN_IMAGE_SIZE} bytes")
        return False
    
    if image_size > MAX_IMAGE_SIZE:
        logger.warning(f"Image validation failed: size {image_size} bytes exceeds maximum {MAX_IMAGE_SIZE} bytes")
        return False
    
    # Check format signature
    if format_type.upper() == 'PNG':
        # PNG signature: 137 80 78 71 13 10 26 10 (hex: 89 50 4E 47 0D 0A 1A 0A)
        png_signature = b'\x89PNG\r\n\x1a\n'
        if not image_bytes.startswith(png_signature):
            logger.warning("Image validation failed: not a valid PNG format")
            return False
    elif format_type.upper() == 'WEBP':
        # WebP signature: RIFF....WEBP
        if not (image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:16]):
            logger.warning("Image validation failed: not a valid WebP format")
            return False
    
    logger.debug(f"Image validation passed: {image_size} bytes ({format_type})")
    return True



def _calculate_backoff_with_jitter(attempt: int) -> float:
    """
    Calculate exponential backoff delay with jitter.
    
    Args:
        attempt: Current retry attempt number (0-indexed)
        
    Returns:
        Delay in seconds with jitter applied
    """
    # Exponential backoff: 1s, 2s, 4s, ...
    base_delay = INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** attempt)
    
    # Add jitter (±20%)
    jitter = base_delay * JITTER_PERCENT * (2 * random.random() - 1)
    delay = base_delay + jitter
    
    return max(0, delay)  # Ensure non-negative


def generate_product_image(
    product: dict,
    model_id: str = DEFAULT_MODEL_ID,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    use_webp: bool = True,
    webp_quality: int = 85
) -> Optional[bytes]:
    """
    Generate product image using Nova Canvas.
    
    Generates a product image based on product data, with retry logic
    and exponential backoff for handling transient failures. Optionally
    converts to WebP format for better compression.
    
    Args:
        product: Product dictionary with name, description, origin, roast_level
        model_id: Bedrock model ID for Nova Canvas
        width: Image width in pixels
        height: Image height in pixels
        max_retries: Maximum retry attempts
        use_webp: Convert PNG to WebP for better compression (default True)
        webp_quality: WebP quality 0-100 (default 85)
        
    Returns:
        Image bytes (WebP or PNG format) or None if generation fails after all retries
    """
    # Generate prompt from product data
    prompt = create_image_prompt(product)
    product_id = product.get("product_id", "unknown")
    
    logger.debug(f"Generating image for product {product_id} with prompt: {prompt[:100]}...")
    
    # Initialize Bedrock runtime client
    try:
        # Use region from environment or default to us-east-1
        import os
        region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION') or 'us-east-1'
        bedrock_runtime = boto3.client('bedrock-runtime', region_name=region)
    except Exception as e:
        logger.error(f"Failed to initialize Bedrock client: {e}")
        return None
    
    # Retry loop
    for attempt in range(max_retries):
        try:
            # Construct API request
            request_body = {
                "taskType": "TEXT_IMAGE",
                "textToImageParams": {
                    "text": prompt
                },
                "imageGenerationConfig": {
                    "numberOfImages": 1,
                    "width": width,
                    "height": height,
                    "cfgScale": 8.0,
                    "seed": random.randint(0, 2147483647)
                }
            }
            
            # Call Nova Canvas API
            logger.debug(f"Calling Bedrock Nova Canvas API (attempt {attempt + 1}/{max_retries})")
            response = bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            
            # Extract image data
            if 'images' not in response_body or len(response_body['images']) == 0:
                logger.warning(f"No images in response for product {product_id}")
                if attempt < max_retries - 1:
                    delay = _calculate_backoff_with_jitter(attempt)
                    logger.info(f"Retrying after {delay:.2f}s...")
                    time.sleep(delay)
                    continue
                return None
            
            # Decode base64 image from response
            image_base64 = response_body['images'][0]
            png_bytes = base64.b64decode(image_base64)
            
            # Validate PNG image
            if not validate_image(png_bytes, 'PNG'):
                logger.warning(f"PNG validation failed for product {product_id}")
                if attempt < max_retries - 1:
                    delay = _calculate_backoff_with_jitter(attempt)
                    logger.info(f"Retrying after {delay:.2f}s...")
                    time.sleep(delay)
                    continue
                return None
            
            # Convert to WebP if requested
            if use_webp:
                try:
                    webp_bytes = convert_png_to_webp(png_bytes, quality=webp_quality)
                    
                    # Validate WebP image
                    if not validate_image(webp_bytes, 'WEBP'):
                        logger.warning(f"WebP validation failed for product {product_id}, using PNG")
                        final_bytes = png_bytes
                    else:
                        final_bytes = webp_bytes
                        logger.info(f"Successfully generated WebP image for product {product_id} "
                                  f"({len(png_bytes)} bytes PNG → {len(webp_bytes)} bytes WebP, "
                                  f"{100 * (1 - len(webp_bytes)/len(png_bytes)):.1f}% reduction)")
                except Exception as e:
                    logger.warning(f"WebP conversion failed for product {product_id}: {e}, using PNG")
                    final_bytes = png_bytes
            else:
                final_bytes = png_bytes
                logger.info(f"Successfully generated PNG image for product {product_id} ({len(png_bytes)} bytes)")
            
            return final_bytes
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            logger.warning(f"Bedrock API error for product {product_id} (attempt {attempt + 1}/{max_retries}): "
                         f"{error_code} - {error_message}")
            
            # Check if we should retry
            if attempt < max_retries - 1:
                # Calculate backoff delay
                delay = _calculate_backoff_with_jitter(attempt)
                logger.info(f"Retrying after {delay:.2f}s...")
                time.sleep(delay)
            else:
                logger.error(f"Failed to generate image for product {product_id} after {max_retries} attempts")
                return None
                
        except Exception as e:
            logger.warning(f"Unexpected error generating image for product {product_id} "
                         f"(attempt {attempt + 1}/{max_retries}): {e}")
            
            if attempt < max_retries - 1:
                delay = _calculate_backoff_with_jitter(attempt)
                logger.info(f"Retrying after {delay:.2f}s...")
                time.sleep(delay)
            else:
                logger.error(f"Failed to generate image for product {product_id} after {max_retries} attempts")
                return None
    
    return None

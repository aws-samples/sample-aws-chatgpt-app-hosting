"""
Upload images to S3 and return CloudFront URLs.

This script provides functionality to upload product images to S3 with proper
metadata and caching headers, then generate CloudFront URLs for CDN delivery.
"""

import boto3
import requests
from pathlib import Path
from typing import Optional
import mimetypes
import sys


def upload_image_to_s3(
    image_source: str,
    product_id: str,
    bucket_name: Optional[str] = None,
    cloudfront_domain: Optional[str] = None
) -> str:
    """Upload image to S3 and return CloudFront URL.
    
    Args:
        image_source: Local file path or HTTP URL
        product_id: Product identifier for S3 key
        bucket_name: S3 bucket name (if None, will auto-detect from CDK or account ID)
        cloudfront_domain: CloudFront distribution domain (required)
        
    Returns:
        CloudFront URL for the uploaded image
        
    Raises:
        ValueError: If image source is invalid or cloudfront_domain is missing
        requests.exceptions.RequestException: If URL download fails
        boto3.exceptions.S3UploadFailedError: If S3 upload fails
    """
    if not cloudfront_domain:
        raise ValueError("cloudfront_domain is required")
    
    # If bucket_name not provided, try to get from CDK outputs or construct from account ID
    if not bucket_name:
        try:
            # Try CDK outputs first
            cfn = boto3.client('cloudformation', region_name='us-east-1')
            response = cfn.describe_stacks(StackName='ImageHostingStack')
            outputs = response['Stacks'][0]['Outputs']
            for output in outputs:
                if output['OutputKey'] == 'ProductImagesBucketName':
                    bucket_name = output['OutputValue']
                    print(f"Using bucket from CDK outputs: {bucket_name}")
                    break
        except Exception:
            pass
        
        # If still not found, construct from account ID
        if not bucket_name:
            try:
                sts = boto3.client('sts', region_name='us-east-1')
                account_id = sts.get_caller_identity()['Account']
                bucket_name = f"chatgpt-apps-aws-{account_id}"
                print(f"Constructed bucket name from account ID: {bucket_name}")
            except Exception as e:
                raise ValueError(f"Could not determine bucket name: {e}")
    
    s3_client = boto3.client('s3', region_name='us-east-1')
    
    # Determine if source is URL or file path
    if image_source.startswith('http://') or image_source.startswith('https://'):
        # Download from URL
        print(f"Downloading image from URL: {image_source}")
        response = requests.get(image_source, timeout=30)
        response.raise_for_status()
        image_data = response.content
        
        # Detect content type from response headers
        content_type = response.headers.get('Content-Type', 'image/png')
    else:
        # Read from local file
        image_path = Path(image_source)
        if not image_path.exists():
            raise ValueError(f"Image file not found: {image_source}")
        
        print(f"Reading image from file: {image_source}")
        image_data = image_path.read_bytes()
        
        # Detect content type from file extension
        content_type, _ = mimetypes.guess_type(str(image_path))
        if not content_type:
            content_type = 'image/png'
    
    # Determine file extension from content type
    ext_map = {
        'image/jpeg': 'jpg',
        'image/jpg': 'jpg',
        'image/png': 'png',
        'image/webp': 'webp',
        'image/gif': 'gif'
    }
    ext = ext_map.get(content_type, 'png')
    
    # Generate S3 key as specified: images/{product_id}.png
    # Note: Task specifies .png extension, but we'll use detected extension
    s3_key = f"images/{product_id}.{ext}"
    
    print(f"Uploading to S3: s3://{bucket_name}/{s3_key}")
    
    # Upload to S3 with required metadata
    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=image_data,
        ContentType=content_type,
        CacheControl='public, max-age=86400, immutable',
        Metadata={
            'product_id': product_id,
            'uploaded_by': 'upload_script'
        }
    )
    
    # Generate CloudFront URL
    # Remove https:// prefix if present in cloudfront_domain
    domain = cloudfront_domain.replace('https://', '').replace('http://', '')
    cloudfront_url = f"https://{domain}/{s3_key}"
    
    print(f"Upload successful! CloudFront URL: {cloudfront_url}")
    
    return cloudfront_url


def main():
    """CLI interface for uploading images."""
    if len(sys.argv) < 3:
        print("Usage: python3 upload_to_s3.py <image_source> <product_id> [cloudfront_domain]")
        print("\nExamples:")
        print("  python3 upload_to_s3.py image.png ethiopian-yirgacheffe d1234.cloudfront.net")
        print("  python3 upload_to_s3.py https://example.com/image.jpg colombian-supremo d1234.cloudfront.net")
        sys.exit(1)
    
    image_source = sys.argv[1]
    product_id = sys.argv[2]
    cloudfront_domain = sys.argv[3] if len(sys.argv) > 3 else None
    
    try:
        url = upload_image_to_s3(
            image_source=image_source,
            product_id=product_id,
            cloudfront_domain=cloudfront_domain
        )
        print(f"\n✓ Success! Image available at: {url}")
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

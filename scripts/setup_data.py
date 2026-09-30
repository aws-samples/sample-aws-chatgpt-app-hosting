#!/usr/bin/env python3
"""
setup_data.py — single, idempotent data-setup entrypoint for the Part 2
AgentCore Coffee app.

Run this once after `cdk deploy --all`:

    export OPENSEARCH_ENDPOINT=<AgentCoreStack.OpenSearchEndpoint>
    python3 scripts/setup_data.py

What it does (all idempotent — safe to re-run):
  1. Creates the OpenSearch Serverless 'coffee-products' index with a
     knn_vector mapping (dimension 1536) if it does not already exist.
  2. OPTIONALLY generates + uploads product images with Nova Canvas when both
     S3_BUCKET and CLOUDFRONT_DOMAIN are set; otherwise it uses the existing
     image_url values already in data/products.json.
  3. Loads data/products.json into OpenSearch, generating Titan embeddings
     (amazon.titan-embed-text-v1) for semantic search.

Environment variables:
  OPENSEARCH_ENDPOINT  (required unless resolvable from the AgentCoreStack
                        CloudFormation output)
  AWS_REGION           (default: us-east-1)
  S3_BUCKET            (optional — enables image generation/upload)
  CLOUDFRONT_DOMAIN    (optional — enables image generation/upload)

Requires: boto3, opensearch-py, requests-aws4auth (see mcp_server/requirements.txt).
Run from the project root so that data/products.json resolves.
"""
import json
import os
import sys
from pathlib import Path

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Make project modules importable (mcp_server, scripts)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from mcp_server.embeddings import EmbeddingsGenerator  # noqa: E402

INDEX_NAME = "coffee-products"
REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
DATA_FILE = PROJECT_ROOT / "data" / "products.json"

INDEX_BODY = {
    "settings": {
        "index": {
            "knn": True,
            "knn.algo_param.ef_search": 512,
        }
    },
    "mappings": {
        "properties": {
            "product_id": {"type": "keyword"},
            "name": {"type": "text"},
            "description": {"type": "text"},
            "origin": {"type": "keyword"},
            "roast_level": {"type": "keyword"},
            "flavor_profile": {"type": "keyword"},
            "price": {"type": "float"},
            "image_url": {"type": "keyword"},
            "description_embedding": {
                "type": "knn_vector",
                "dimension": 1536,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "nmslib",
                    "parameters": {"ef_construction": 512, "m": 16},
                },
            },
        }
    },
}


def _log(msg: str) -> None:
    print(msg, flush=True)


def resolve_endpoint() -> str:
    """Resolve the OpenSearch endpoint from env or the AgentCoreStack output."""
    endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "").strip()
    if endpoint:
        return endpoint.replace("https://", "")

    _log("OPENSEARCH_ENDPOINT not set — trying AgentCoreStack CloudFormation output...")
    try:
        cfn = boto3.client("cloudformation", region_name=REGION)
        stacks = cfn.describe_stacks(StackName="AgentCoreStack")["Stacks"]
        for output in stacks[0].get("Outputs", []):
            if output["OutputKey"] == "OpenSearchEndpoint":
                return output["OutputValue"].replace("https://", "")
    except Exception as e:  # noqa: BLE001
        _log(f"  Could not read AgentCoreStack output: {e}")

    _log("ERROR: OpenSearch endpoint not found.")
    _log("  Set it explicitly: export OPENSEARCH_ENDPOINT=<AgentCoreStack.OpenSearchEndpoint>")
    sys.exit(1)


def build_client(endpoint: str) -> OpenSearch:
    credentials = boto3.Session().get_credentials()
    if credentials is None:
        _log("ERROR: No AWS credentials found. Configure credentials and retry.")
        sys.exit(1)
    awsauth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        REGION,
        "aoss",
        session_token=credentials.token,
    )
    return OpenSearch(
        hosts=[{"host": endpoint, "port": 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=60,
    )


def ensure_index(client: OpenSearch) -> None:
    _log(f"\n[1/3] Ensuring index '{INDEX_NAME}' exists...")
    try:
        if client.indices.exists(index=INDEX_NAME):
            _log(f"  ✅ Index '{INDEX_NAME}' already exists")
            return
    except Exception as e:  # noqa: BLE001
        _log(f"  (exists-check failed, will attempt create): {e}")
    try:
        client.indices.create(index=INDEX_NAME, body=INDEX_BODY)
        _log(f"  ✅ Created index '{INDEX_NAME}' with knn_vector mapping (dim 1536)")
    except Exception as e:  # noqa: BLE001
        # If it already exists (race / eventual consistency), that's fine.
        if "resource_already_exists" in str(e) or "already exists" in str(e):
            _log(f"  ✅ Index '{INDEX_NAME}' already exists")
        else:
            _log(f"  ❌ Failed to create index: {e}")
            sys.exit(1)


def maybe_generate_images(products: list) -> None:
    """Generate + upload images only if S3_BUCKET and CLOUDFRONT_DOMAIN are set."""
    bucket = os.environ.get("S3_BUCKET", "").strip()
    cloudfront = os.environ.get("CLOUDFRONT_DOMAIN", "").strip()
    if not bucket or not cloudfront:
        _log("\n[2/3] Skipping image generation (S3_BUCKET/CLOUDFRONT_DOMAIN not set).")
        _log("  Using existing image_url values from data/products.json.")
        return

    cloudfront = cloudfront.replace("https://", "").replace("http://", "")
    _log(f"\n[2/3] Generating images with Nova Canvas -> s3://{bucket} ({cloudfront})...")
    try:
        from image_generator import generate_product_image
        from upload_to_s3 import upload_image_to_s3
        from tempfile import NamedTemporaryFile
    except Exception as e:  # noqa: BLE001
        _log(f"  ⚠️  Image helpers unavailable ({e}); using existing image_url values.")
        return

    updated = 0
    for i, product in enumerate(products, 1):
        # Idempotent: skip products already pointing at this CloudFront domain
        if product.get("image_url", "").startswith(f"https://{cloudfront}"):
            continue
        try:
            _log(f"  [{i}/{len(products)}] {product['name']}: generating...")
            image_bytes = generate_product_image(product=product, use_webp=False, max_retries=3)
            if not image_bytes:
                _log("    ✗ generation returned no bytes; skipping")
                continue
            with NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(image_bytes)
                tmp.flush()
                tmp_path = tmp.name
            try:
                url = upload_image_to_s3(
                    image_source=tmp_path,
                    product_id=product["product_id"],
                    bucket_name=bucket,
                    cloudfront_domain=cloudfront,
                )
                product["image_url"] = url
                updated += 1
                _log(f"    ✓ {url}")
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001
            _log(f"    ✗ error: {e}")

    if updated:
        with open(DATA_FILE, "w") as f:
            json.dump({"products": products}, f, indent=2)
        _log(f"  ✅ Updated {updated} image_url(s) in {DATA_FILE}")


def load_products(client: OpenSearch, products: list) -> None:
    _log(f"\n[3/3] Embedding + indexing {len(products)} products...")
    embeddings_gen = EmbeddingsGenerator(region=REGION)
    indexed = 0
    for i, product in enumerate(products, 1):
        try:
            text = (
                f"{product['name']} {product['description']} {product['origin']} "
                f"{' '.join(product.get('flavor_profile', []))}"
            )
            doc = dict(product)
            doc["description_embedding"] = embeddings_gen.generate_embedding(text)
            # OpenSearch Serverless does not support client-specified _id;
            # product_id is kept as a document field (tools query on that field).
            client.index(index=INDEX_NAME, body=doc)
            indexed += 1
            _log(f"  [{i}/{len(products)}] {product['name']} ✅")
        except Exception as e:  # noqa: BLE001
            _log(f"  [{i}/{len(products)}] {product['name']} ❌ {e}")
    _log(f"\n✅ Done — indexed {indexed}/{len(products)} products into '{INDEX_NAME}'.")


def main() -> None:
    _log("=" * 64)
    _log("Coffee AgentCore — data setup")
    _log("=" * 64)

    if not DATA_FILE.exists():
        _log(f"ERROR: {DATA_FILE} not found. Run from the project root.")
        sys.exit(1)

    endpoint = resolve_endpoint()
    _log(f"OpenSearch endpoint: {endpoint}")
    _log(f"Region: {REGION}")

    with open(DATA_FILE) as f:
        products = json.load(f)["products"]
    _log(f"Loaded {len(products)} products from {DATA_FILE}")

    client = build_client(endpoint)
    ensure_index(client)
    maybe_generate_images(products)
    load_products(client, products)


if __name__ == "__main__":
    main()

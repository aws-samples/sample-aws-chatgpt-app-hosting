"""
OpenSearch client for product search
Handles connection, semantic search, and filtered search
"""
import os
import logging
from typing import List, Dict, Optional, Tuple
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import boto3

logger = logging.getLogger(__name__)

def normalize_filters(filters: Optional[Dict]) -> Optional[Dict]:
    """Normalize incoming filter values so ChatGPT-supplied capitalized values
    (e.g. "Light", "Ethiopia", ["Fruity"]) match the lowercase keyword values
    stored in OpenSearch. Returns a new dict; leaves price_range untouched.
    """
    if not filters:
        return filters
    normalized = dict(filters)
    if "roast_level" in normalized and isinstance(normalized["roast_level"], str):
        normalized["roast_level"] = normalized["roast_level"].lower().strip()
    # Origin keyword values are stored Title Case in the catalog (e.g.
    # "Ethiopia"), so Title-case the filter to match what ChatGPT sends
    # ("ethiopia"/"ETHIOPIA"/"Ethiopia") -> "Ethiopia".
    if "origin" in normalized and isinstance(normalized["origin"], str):
        normalized["origin"] = normalized["origin"].strip().title()
    if "flavor_profile" in normalized:
        fp = normalized["flavor_profile"]
        if isinstance(fp, list):
            normalized["flavor_profile"] = [
                f.lower().strip() if isinstance(f, str) else f for f in fp
            ]
        elif isinstance(fp, str):
            normalized["flavor_profile"] = fp.lower().strip()
    return normalized

def get_opensearch_endpoint_from_ssm() -> Optional[str]:
    """Fetch OpenSearch endpoint from SSM Parameter Store"""
    try:
        ssm = boto3.client('ssm', region_name=os.getenv("AWS_REGION", "us-east-1"))
        response = ssm.get_parameter(Name='/coffee/opensearch/endpoint')
        return response['Parameter']['Value']
    except Exception as e:
        logger.warning(f"Could not fetch OpenSearch endpoint from SSM: {e}")
        return None

class OpenSearchClient:
    """Client for interacting with OpenSearch Serverless"""
    
    def __init__(self, endpoint: Optional[str] = None, region: Optional[str] = None):
        """
        Initialize OpenSearch client with AWS SigV4 authentication
        
        Args:
            endpoint: OpenSearch endpoint URL (defaults to OPENSEARCH_ENDPOINT env var, then SSM)
            region: AWS region (defaults to AWS_REGION env var)
        """
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        
        # Try to get endpoint from: 1) parameter, 2) env var, 3) SSM
        self.endpoint = endpoint or os.getenv("OPENSEARCH_ENDPOINT")
        if not self.endpoint:
            logger.info("OPENSEARCH_ENDPOINT not set, trying SSM...")
            self.endpoint = get_opensearch_endpoint_from_ssm()
        
        self.index_name = "coffee-products"
        
        if not self.endpoint:
            raise ValueError("OpenSearch endpoint not provided")
        
        # Set up AWS SigV4 authentication
        credentials = boto3.Session().get_credentials()
        self.awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            self.region,
            'aoss',  # OpenSearch Serverless service name
            session_token=credentials.token
        )
        
        # Initialize OpenSearch client
        self.client = OpenSearch(
            hosts=[{'host': self.endpoint.replace('https://', ''), 'port': 443}],
            http_auth=self.awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=30
        )
        
        logger.info(f"OpenSearch client initialized for endpoint: {self.endpoint}")
    
    def semantic_search(
        self,
        embedding: List[float],
        k: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Perform semantic search using vector embeddings
        
        Args:
            embedding: Query embedding vector
            k: Number of results to return
            filters: Optional filters (origin, roast_level, price_range)
        
        Returns:
            List of product documents
        """
        try:
            # Build query with vector search
            query = {
                "size": k,
                "query": {
                    "bool": {
                        "must": [
                            {
                                "knn": {
                                    "description_embedding": {
                                        "vector": embedding,
                                        "k": k
                                    }
                                }
                            }
                        ]
                    }
                }
            }
            
            # Add filters if provided
            if filters:
                filters = normalize_filters(filters)
                filter_clauses = []
                
                if "origin" in filters:
                    filter_clauses.append({"term": {"origin": filters["origin"]}})
                
                if "roast_level" in filters:
                    filter_clauses.append({"term": {"roast_level": filters["roast_level"]}})
                
                if "price_range" in filters and len(filters["price_range"]) == 2:
                    min_price, max_price = filters["price_range"]
                    filter_clauses.append({
                        "range": {
                            "price": {
                                "gte": min_price,
                                "lte": max_price
                            }
                        }
                    })
                
                if "flavor_profile" in filters:
                    # Match any of the specified flavor profiles
                    if isinstance(filters["flavor_profile"], list):
                        filter_clauses.append({
                            "terms": {"flavor_profile": filters["flavor_profile"]}
                        })
                    else:
                        filter_clauses.append({
                            "term": {"flavor_profile": filters["flavor_profile"]}
                        })
                
                if filter_clauses:
                    query["query"]["bool"]["filter"] = filter_clauses
            
            logger.info(f"Executing semantic search with k={k}, filters={filters}")
            response = self.client.search(index=self.index_name, body=query)
            
            # Extract and return products
            products = []
            for hit in response["hits"]["hits"]:
                product = hit["_source"]
                product["_score"] = hit["_score"]
                products.append(product)
            
            logger.info(f"Found {len(products)} products")
            return products
            
        except Exception as e:
            logger.error(f"Error during semantic search: {str(e)}")
            raise
    
    def filtered_search(
        self,
        filters: Dict,
        size: int = 20
    ) -> List[Dict]:
        """
        Perform filtered search with exact attribute matching
        
        Args:
            filters: Filter criteria (origin, roast_level, price_range, flavor_profile)
            size: Maximum number of results
        
        Returns:
            List of product documents
        """
        try:
            filters = normalize_filters(filters)
            filter_clauses = []
            
            if "origin" in filters:
                filter_clauses.append({"term": {"origin": filters["origin"]}})
            
            if "roast_level" in filters:
                filter_clauses.append({"term": {"roast_level": filters["roast_level"]}})
            
            if "price_range" in filters and len(filters["price_range"]) == 2:
                min_price, max_price = filters["price_range"]
                filter_clauses.append({
                    "range": {
                        "price": {
                            "gte": min_price,
                            "lte": max_price
                        }
                    }
                })
            
            if "flavor_profile" in filters:
                if isinstance(filters["flavor_profile"], list):
                    filter_clauses.append({
                        "terms": {"flavor_profile": filters["flavor_profile"]}
                    })
                else:
                    filter_clauses.append({
                        "term": {"flavor_profile": filters["flavor_profile"]}
                    })
            
            query = {
                "size": size,
                "query": {
                    "bool": {
                        "filter": filter_clauses
                    }
                }
            }
            
            logger.info(f"Executing filtered search with filters={filters}")
            response = self.client.search(index=self.index_name, body=query)
            
            # Extract and return products
            products = []
            for hit in response["hits"]["hits"]:
                product = hit["_source"]
                products.append(product)
            
            logger.info(f"Found {len(products)} products")
            return products
            
        except Exception as e:
            logger.error(f"Error during filtered search: {str(e)}")
            raise
    
    def get_product_by_id(self, product_id: str) -> Optional[Dict]:
        """
        Retrieve a specific product by ID
        
        Args:
            product_id: Product identifier
        
        Returns:
            Product document or None if not found
        """
        try:
            query = {
                "query": {
                    "term": {
                        "product_id": product_id
                    }
                }
            }
            
            response = self.client.search(index=self.index_name, body=query)
            
            if response["hits"]["total"]["value"] > 0:
                return response["hits"]["hits"][0]["_source"]
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving product {product_id}: {str(e)}")
            raise

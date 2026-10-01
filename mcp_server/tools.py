"""
MCP Tools for Coffee Discovery
Implements search_products, get_product_details, and refine_preferences tools
"""
import logging
from typing import Dict, List, Optional, Any
from mcp.types import CallToolResult, TextContent
from opensearch_client import OpenSearchClient
from embeddings import EmbeddingsGenerator
from preference_parser import parse_preferences

logger = logging.getLogger(__name__)

# Initialize clients (will be reused across requests)
opensearch_client = None
embeddings_generator = None

def get_opensearch_client() -> OpenSearchClient:
    """Get or create OpenSearch client"""
    global opensearch_client
    if opensearch_client is None:
        opensearch_client = OpenSearchClient()
    return opensearch_client

def get_embeddings_generator() -> EmbeddingsGenerator:
    """Get or create embeddings generator"""
    global embeddings_generator
    if embeddings_generator is None:
        embeddings_generator = EmbeddingsGenerator()
    return embeddings_generator

def format_product_for_response(product: Dict) -> Dict:
    """
    Format product for response, ensuring all required fields are present
    
    Args:
        product: Product document from OpenSearch
    
    Returns:
        Formatted product dictionary with CloudFront image URL
    """
    formatted = {
        "product_id": product.get("product_id", ""),
        "name": product.get("name", ""),
        "description": product.get("description", ""),
        "origin": product.get("origin", ""),
        "roast_level": product.get("roast_level", ""),
        "flavor_profile": product.get("flavor_profile", []),
        "price": product.get("price", 0.0),
        "image_url": product.get("image_url", "")  # CloudFront URL
    }
    
    return formatted

def search_products(preferences: str, filters: Optional[Dict] = None) -> CallToolResult:
    """
    Search for coffee products based on natural language preferences

    Args:
        preferences: Natural language description of coffee preferences
        filters: Optional filters (origin, roast_level, price_range, flavor_profile)

    Returns:
        CallToolResult with structuredContent for widget rendering
    """
    try:
        logger.info(f"search_products called with preferences: {preferences}, filters: {filters}")

        # Validate input
        if not preferences or not preferences.strip():
            return CallToolResult(
                content=[TextContent(type="text", text="Please describe what kind of coffee you're looking for.")],
                structuredContent={"products": [], "message": "No preferences provided"}
            )

        # Parse natural language preferences
        parsed_attrs = parse_preferences(preferences)

        # Merge parsed attributes with explicit filters
        combined_filters = {}
        if parsed_attrs:
            combined_filters.update(parsed_attrs)
        if filters:
            combined_filters.update(filters)

        # Generate embedding for semantic search
        embeddings_gen = get_embeddings_generator()
        embedding = embeddings_gen.generate_embedding(preferences)

        # Perform semantic search with filters
        os_client = get_opensearch_client()
        products = os_client.semantic_search(
            embedding=embedding,
            k=10,
            filters=combined_filters if combined_filters else None
        )

        # Format products for response
        formatted_products = [format_product_for_response(p) for p in products]

        # Create response message
        if formatted_products:
            message = f"Found {len(formatted_products)} coffee products matching your preferences."
            if combined_filters:
                filter_desc = []
                if "origin" in combined_filters:
                    filter_desc.append(f"from {combined_filters['origin']}")
                if "roast_level" in combined_filters:
                    filter_desc.append(f"{combined_filters['roast_level']} roast")
                if "price_range" in combined_filters:
                    min_p, max_p = combined_filters["price_range"]
                    filter_desc.append(f"${min_p:.2f}-${max_p:.2f}")
                if filter_desc:
                    message += f" ({', '.join(filter_desc)})"
        else:
            message = "No products found matching your preferences. Try adjusting your criteria."

        return CallToolResult(
            content=[TextContent(type="text", text=message)],
            structuredContent={"products": formatted_products, "message": message}
        )

    except Exception as e:
        logger.error(f"Error in search_products: {str(e)}", exc_info=True)
        return CallToolResult(
            content=[TextContent(type="text", text=f"I encountered an error while searching for products: {str(e)}")],
            structuredContent={"error": True, "message": str(e), "products": []}
        )

def get_product_details(product_id: str) -> CallToolResult:
    """
    Get detailed information about a specific product

    Args:
        product_id: Product identifier

    Returns:
        CallToolResult with structuredContent for widget rendering
    """
    try:
        logger.info(f"get_product_details called with product_id: {product_id}")

        if not product_id or not product_id.strip():
            return CallToolResult(
                content=[TextContent(type="text", text="Please provide a product ID.")],
                structuredContent={"products": [], "message": "No product ID provided"}
            )

        os_client = get_opensearch_client()
        product = os_client.get_product_by_id(product_id)

        if product:
            formatted_product = format_product_for_response(product)
            message = f"Here are the details for {product.get('name', 'this product')}."
            return CallToolResult(
                content=[TextContent(type="text", text=message)],
                structuredContent={"products": [formatted_product], "message": message}
            )
        else:
            message = f"Product with ID '{product_id}' not found."
            return CallToolResult(
                content=[TextContent(type="text", text=message)],
                structuredContent={"products": [], "message": message}
            )

    except Exception as e:
        logger.error(f"Error in get_product_details: {str(e)}", exc_info=True)
        return CallToolResult(
            content=[TextContent(type="text", text=f"I encountered an error while retrieving product details: {str(e)}")],
            structuredContent={"error": True, "message": str(e), "products": []}
        )

def refine_preferences(
    exclude: Optional[List[str]] = None,
    similar_to: Optional[str] = None,
    filters: Optional[Dict] = None
) -> CallToolResult:
    """
    Refine product search with exclusions and similarity

    Args:
        exclude: List of attributes to exclude (origins, roast levels, flavors)
        similar_to: Product ID to find similar products
        filters: Optional filters (origin, roast_level, price_range, flavor_profile)

    Returns:
        CallToolResult with structuredContent for widget rendering
    """
    try:
        logger.info(f"refine_preferences called with exclude: {exclude}, similar_to: {similar_to}, filters: {filters}")

        os_client = get_opensearch_client()
        products = []

        if similar_to:
            reference_product = os_client.get_product_by_id(similar_to)
            if reference_product:
                embeddings_gen = get_embeddings_generator()
                embedding = embeddings_gen.generate_embedding(reference_product.get("description", ""))
                products = os_client.semantic_search(embedding=embedding, k=10, filters=filters)
                products = [p for p in products if p.get("product_id") != similar_to]
            else:
                logger.warning(f"Reference product {similar_to} not found")
        else:
            if filters:
                products = os_client.filtered_search(filters=filters, size=20)

        if exclude and products:
            filtered_products = []
            for product in products:
                should_exclude = False
                for exclusion in exclude:
                    exclusion_lower = exclusion.lower().strip()
                    exclusion_normalized = exclusion_lower.replace(" roast", "").strip()
                    if product.get("origin", "").lower() == exclusion_normalized:
                        should_exclude = True
                        break
                    roast_level = product.get("roast_level", "").lower()
                    if roast_level == exclusion_normalized or roast_level == exclusion_lower:
                        should_exclude = True
                        break
                    flavor_profiles = product.get("flavor_profile", [])
                    if any(f.lower() == exclusion_normalized or f.lower() == exclusion_lower for f in flavor_profiles):
                        should_exclude = True
                        break
                if not should_exclude:
                    filtered_products.append(product)
            products = filtered_products

        formatted_products = [format_product_for_response(p) for p in products]

        if formatted_products:
            message = f"Found {len(formatted_products)} products"
            if similar_to:
                message += f" similar to your selection"
            if exclude:
                message += f" (excluding: {', '.join(exclude)})"
            message += "."
        else:
            message = "No products found matching your refined criteria. Try adjusting your filters."

        return CallToolResult(
            content=[TextContent(type="text", text=message)],
            structuredContent={"products": formatted_products, "message": message}
        )

    except Exception as e:
        logger.error(f"Error in refine_preferences: {str(e)}", exc_info=True)
        return CallToolResult(
            content=[TextContent(type="text", text=f"I encountered an error while refining preferences: {str(e)}")],
            structuredContent={"error": True, "message": str(e), "products": []}
        )

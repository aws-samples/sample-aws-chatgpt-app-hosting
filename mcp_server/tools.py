"""
MCP Tools for Coffee Discovery
Implements search_products, get_product_details, and refine_preferences tools
"""
import logging
import base64
import requests
from typing import Dict, List, Optional, Any
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
        Formatted product dictionary
    """
    return {
        "product_id": product.get("product_id", ""),
        "name": product.get("name", ""),
        "description": product.get("description", ""),
        "origin": product.get("origin", ""),
        "roast_level": product.get("roast_level", ""),
        "flavor_profile": product.get("flavor_profile", []),
        "price": product.get("price", 0.0),
        "image_url": product.get("image_url", "")
    }

def fetch_image_as_base64(image_url: str, timeout: int = 5) -> Optional[str]:
    """
    Fetch an image from URL and convert to base64
    
    Args:
        image_url: URL of the image to fetch
        timeout: Request timeout in seconds
    
    Returns:
        Base64-encoded image data or None if fetch fails
    """
    try:
        response = requests.get(image_url, timeout=timeout)
        response.raise_for_status()
        return base64.b64encode(response.content).decode('utf-8')
    except Exception as e:
        logger.warning(f"Failed to fetch image from {image_url}: {e}")
        return None

def format_products_with_images(products: List[Dict], intro_message: str = "") -> List[Dict]:
    """
    Format products as rich text content (ChatGPT doesn't support images yet)
    
    Args:
        products: List of formatted product dictionaries
        intro_message: Optional introductory message
    
    Returns:
        List with single text content block containing all products
    """
    # Build rich text response with clickable image links
    content_text = intro_message
    if intro_message:
        content_text += "\n\n"
    
    for i, product in enumerate(products, 1):
        content_text += f"### {i}. {product['name']}\n\n"
        
        # Add clickable image link (ChatGPT may render as link)
        if product.get('image_url'):
            content_text += f"🖼️ [View Product Image]({product['image_url']})\n\n"
        
        # Product details with emojis for visual appeal
        content_text += f"📍 **Origin:** {product['origin']}\n"
        content_text += f"☕ **Roast Level:** {product['roast_level'].title()}\n"
        content_text += f"💰 **Price:** ${product['price']:.2f}\n"
        content_text += f"🌟 **Flavors:** {', '.join(product['flavor_profile'])}\n\n"
        content_text += f"{product['description']}\n\n"
        content_text += "---\n\n"
    
    return [
        {
            "type": "text",
            "text": content_text
        }
    ]

def search_products(preferences: str, filters: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Search for coffee products based on natural language preferences
    
    Args:
        preferences: Natural language description of coffee preferences
        filters: Optional filters (origin, roast_level, price_range, flavor_profile)
    
    Returns:
        Dictionary with products array and message
    """
    try:
        logger.info(f"search_products called with preferences: {preferences}, filters: {filters}")
        
        # Validate input
        if not preferences or not preferences.strip():
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Please describe what kind of coffee you're looking for."
                    }
                ],
                "structuredContent": {
                    "products": [],
                    "message": "No preferences provided"
                }
            }
        
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
        
        # Format products for response and deduplicate by product_id
        seen_ids = set()
        formatted_products = []
        for p in products:
            product_id = p.get("product_id")
            if product_id and product_id not in seen_ids:
                seen_ids.add(product_id)
                formatted_products.append(format_product_for_response(p))
        
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
        
        # Format products with images as content blocks
        content_blocks = format_products_with_images(formatted_products, message)
        
        # Return BOTH content and structuredContent (working example does this!)
        return {
            "content": content_blocks,
            "structuredContent": {
                "products": formatted_products,
                "message": message
            }
        }
        
    except Exception as e:
        logger.error(f"Error in search_products: {str(e)}", exc_info=True)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"I encountered an error while searching for products: {str(e)}"
                }
            ],
            "structuredContent": {
                "error": True,
                "message": str(e),
                "products": []
            }
        }

def get_product_details(product_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific product
    
    Args:
        product_id: Product identifier
    
    Returns:
        Dictionary with product details and message
    """
    try:
        logger.info(f"get_product_details called with product_id: {product_id}")
        
        # Validate input
        if not product_id or not product_id.strip():
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Please provide a product ID."
                    }
                ],
                "structuredContent": {
                    "products": [],
                    "message": "No product ID provided"
                }
            }
        
        # Query OpenSearch by product ID
        os_client = get_opensearch_client()
        product = os_client.get_product_by_id(product_id)
        
        if product:
            formatted_product = format_product_for_response(product)
            
            # Build detailed product view with clickable image link
            details_text = f"# {formatted_product['name']}\n\n"
            
            # Add clickable image link
            if formatted_product.get('image_url'):
                details_text += f"🖼️ [View Product Image]({formatted_product['image_url']})\n\n"
            
            # Detailed product information
            details_text += f"📍 **Origin:** {formatted_product['origin']}\n"
            details_text += f"☕ **Roast Level:** {formatted_product['roast_level'].title()}\n"
            details_text += f"🌟 **Flavor Profile:** {', '.join(formatted_product['flavor_profile'])}\n"
            details_text += f"💰 **Price:** ${formatted_product['price']:.2f}\n\n"
            details_text += f"**Description:**\n{formatted_product['description']}\n\n"
            
            # Add brewing recommendations based on roast level
            details_text += "**☕ Brewing Recommendations:**\n"
            if formatted_product['roast_level'] == 'light':
                details_text += "- **Best for:** Pour-over, V60, Chemex, Cold brew\n"
                details_text += "- **Grind:** Medium-fine to medium\n"
                details_text += "- **Water temp:** 195-205°F (90-96°C)\n"
            elif formatted_product['roast_level'] == 'medium':
                details_text += "- **Best for:** Drip coffee, French press, Pour-over\n"
                details_text += "- **Grind:** Medium\n"
                details_text += "- **Water temp:** 200-205°F (93-96°C)\n"
            elif formatted_product['roast_level'] == 'dark':
                details_text += "- **Best for:** Espresso, French press, Moka pot\n"
                details_text += "- **Grind:** Fine to medium\n"
                details_text += "- **Water temp:** 190-200°F (88-93°C)\n"
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": details_text
                    }
                ],
                "structuredContent": {
                    "products": [formatted_product],
                    "message": f"Details for {formatted_product['name']}"
                }
            }
        else:
            message = f"Product with ID '{product_id}' not found."
            return {
                "content": [
                    {
                        "type": "text",
                        "text": message
                    }
                ],
                "structuredContent": {
                    "products": [],
                    "message": message
                }
            }
        
    except Exception as e:
        logger.error(f"Error in get_product_details: {str(e)}", exc_info=True)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"I encountered an error while retrieving product details: {str(e)}"
                }
            ],
            "structuredContent": {
                "error": True,
                "message": str(e),
                "products": []
            }
        }

def refine_preferences(
    exclude: Optional[List[str]] = None,
    similar_to: Optional[str] = None,
    filters: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Refine product search with exclusions and similarity
    
    Args:
        exclude: List of attributes to exclude (origins, roast levels, flavors)
        similar_to: Product ID to find similar products
        filters: Optional filters (origin, roast_level, price_range, flavor_profile)
    
    Returns:
        Dictionary with refined products array and message
    """
    try:
        logger.info(f"refine_preferences called with exclude: {exclude}, similar_to: {similar_to}, filters: {filters}")
        
        os_client = get_opensearch_client()
        products = []
        
        # Handle similarity search
        if similar_to:
            # Get the reference product
            reference_product = os_client.get_product_by_id(similar_to)
            
            if reference_product:
                # Generate embedding from reference product description
                embeddings_gen = get_embeddings_generator()
                embedding = embeddings_gen.generate_embedding(reference_product.get("description", ""))
                
                # Search for similar products
                products = os_client.semantic_search(
                    embedding=embedding,
                    k=10,
                    filters=filters
                )
                
                # Remove the reference product itself from results
                products = [p for p in products if p.get("product_id") != similar_to]
            else:
                logger.warning(f"Reference product {similar_to} not found")
        else:
            # Perform filtered search without similarity
            if filters:
                products = os_client.filtered_search(filters=filters, size=20)
        
        # Apply exclusion filters
        if exclude and products:
            filtered_products = []
            for product in products:
                should_exclude = False
                
                for exclusion in exclude:
                    exclusion_lower = exclusion.lower()
                    
                    # Check if exclusion matches origin
                    if product.get("origin", "").lower() == exclusion_lower:
                        should_exclude = True
                        break
                    
                    # Check if exclusion matches roast level
                    if product.get("roast_level", "").lower() == exclusion_lower:
                        should_exclude = True
                        break
                    
                    # Check if exclusion matches any flavor profile
                    flavor_profiles = product.get("flavor_profile", [])
                    if any(f.lower() == exclusion_lower for f in flavor_profiles):
                        should_exclude = True
                        break
                
                if not should_exclude:
                    filtered_products.append(product)
            
            products = filtered_products
        
        # Format products for response and deduplicate by product_id
        seen_ids = set()
        formatted_products = []
        for p in products:
            product_id = p.get("product_id")
            if product_id and product_id not in seen_ids:
                seen_ids.add(product_id)
                formatted_products.append(format_product_for_response(p))
        
        # Create response message
        if formatted_products:
            message = f"Found {len(formatted_products)} products"
            if similar_to:
                message += f" similar to your selection"
            if exclude:
                message += f" (excluding: {', '.join(exclude)})"
            message += "."
        else:
            message = "No products found matching your refined criteria. Try adjusting your filters."
        
        # Format products with images as content blocks
        content_blocks = format_products_with_images(formatted_products, message)
        
        # Return BOTH content and structuredContent (working example does this!)
        return {
            "content": content_blocks,
            "structuredContent": {
                "products": formatted_products,
                "message": message
            }
        }
        
    except Exception as e:
        logger.error(f"Error in refine_preferences: {str(e)}", exc_info=True)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"I encountered an error while refining preferences: {str(e)}"
                }
            ],
            "structuredContent": {
                "error": True,
                "message": str(e),
                "products": []
            }
        }

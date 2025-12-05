"""
Preference parser for extracting coffee attributes from natural language
"""
import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Known coffee attributes
ORIGINS = [
    "ethiopia", "ethiopian", "colombia", "colombian", "brazil", "brazilian",
    "kenya", "kenyan", "guatemala", "guatemalan", "costa rica", "costa rican",
    "sumatra", "sumatran", "yemen", "yemeni", "peru", "peruvian"
]

ROAST_LEVELS = ["light", "medium", "dark", "blonde", "city", "french", "italian"]

FLAVOR_PROFILES = [
    "fruity", "nutty", "chocolatey", "chocolate", "floral", "earthy",
    "spicy", "sweet", "citrus", "berry", "caramel", "vanilla"
]

def parse_preferences(preferences: str) -> Dict:
    """
    Parse natural language preferences into structured attributes
    
    Args:
        preferences: Natural language preference string
    
    Returns:
        Dictionary with extracted attributes (origin, roast_level, flavor_profile, price_range)
    """
    if not preferences:
        return {}
    
    try:
        # Normalize input
        text = preferences.lower().strip()
        
        attributes = {}
        
        # Extract origin
        for origin in ORIGINS:
            if origin in text:
                # Normalize to country name
                if "ethiopian" in origin or "ethiopia" in origin:
                    attributes["origin"] = "Ethiopia"
                elif "colombian" in origin or "colombia" in origin:
                    attributes["origin"] = "Colombia"
                elif "brazilian" in origin or "brazil" in origin:
                    attributes["origin"] = "Brazil"
                elif "kenyan" in origin or "kenya" in origin:
                    attributes["origin"] = "Kenya"
                elif "guatemalan" in origin or "guatemala" in origin:
                    attributes["origin"] = "Guatemala"
                elif "costa rica" in origin or "costa rican" in origin:
                    attributes["origin"] = "Costa Rica"
                elif "sumatran" in origin or "sumatra" in origin:
                    attributes["origin"] = "Sumatra"
                elif "yemeni" in origin or "yemen" in origin:
                    attributes["origin"] = "Yemen"
                elif "peruvian" in origin or "peru" in origin:
                    attributes["origin"] = "Peru"
                break
        
        # Extract roast level
        for roast in ROAST_LEVELS:
            if roast in text:
                # Normalize roast level
                if roast in ["light", "blonde"]:
                    attributes["roast_level"] = "light"
                elif roast in ["medium", "city"]:
                    attributes["roast_level"] = "medium"
                elif roast in ["dark", "french", "italian"]:
                    attributes["roast_level"] = "dark"
                break
        
        # Extract flavor profiles
        flavors = []
        for flavor in FLAVOR_PROFILES:
            if flavor in text:
                # Normalize flavor names
                if flavor == "chocolate":
                    flavor = "chocolatey"
                if flavor not in flavors:
                    flavors.append(flavor)
        
        if flavors:
            attributes["flavor_profile"] = flavors
        
        # Extract price range
        # Look for patterns like "$10-20", "under $20", "$15 to $25", "budget", "premium"
        price_patterns = [
            r'\$(\d+)\s*-\s*\$?(\d+)',  # $10-$20 or $10-20
            r'\$(\d+)\s+to\s+\$?(\d+)',  # $10 to $20
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text)
            if match:
                min_price = float(match.group(1))
                max_price = float(match.group(2))
                attributes["price_range"] = [min_price, max_price]
                break
        
        # Check for price keywords
        if "price_range" not in attributes:
            if "budget" in text or "cheap" in text or "affordable" in text:
                attributes["price_range"] = [12, 15]
            elif "premium" in text or "expensive" in text or "high-end" in text:
                attributes["price_range"] = [23, 35]
            elif "mid-range" in text or "moderate" in text:
                attributes["price_range"] = [16, 22]
            elif "under" in text:
                # Look for "under $X"
                match = re.search(r'under\s+\$?(\d+)', text)
                if match:
                    max_price = float(match.group(1))
                    attributes["price_range"] = [0, max_price]
        
        logger.info(f"Parsed preferences: {attributes}")
        return attributes
        
    except Exception as e:
        logger.error(f"Error parsing preferences: {str(e)}")
        # Return empty dict on error - graceful degradation
        return {}

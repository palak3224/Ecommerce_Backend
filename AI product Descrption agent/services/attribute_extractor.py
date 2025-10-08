from typing import Dict
import json
from services.gemini_integration import call_gemini

def extract_attributes(product_name: str, image_analysis: str, image_attributes: str) -> Dict:
    """
    Dynamically extract product attributes using AI.
    
    Args:
        product_name: Name of the product
        image_analysis: Detailed image analysis from Gemini
        image_attributes: Attribute extraction from image
    
    Returns:
        Dictionary of extracted attributes
    """
    prompt = f"""
Extract ALL relevant product attributes from the following information. 

Product Name: {product_name}
Image Analysis: {image_analysis}
Image Attributes: {image_attributes}

Extract as many relevant attributes as you can find. Common attributes include but are not limited to:
- brand
- model_name
- color (all colors if multiple)
- material
- size/dimensions
- processor (for electronics)
- RAM/storage (for computers)
- screen_size (for displays)
- gender (men/women/unisex/kids for apparel)
- product_type (laptop, phone, shirt, etc.)
- style
- weight
- battery_capacity
- connectivity (WiFi, Bluetooth, etc.)
- operating_system
- graphics_card
- storage_type (SSD, HDD)
- any other technical specifications

Only include attributes that you can confidently identify. If an attribute is not clear, omit it.
Output as a flat JSON object with attribute names as keys and their values as strings.

Example format:
{{"brand": "HP", "model_name": "Victus", "processor": "Intel Core i5 12th Gen", "product_type": "Gaming Laptop"}}
"""
    
    try:
        result = call_gemini(prompt, return_raw=False)
        
        # If it's already a dict, return it
        if isinstance(result, dict) and "error" not in result:
            return result
        
        # If there's an error, try to parse raw_text
        if isinstance(result, dict) and "raw_text" in result:
            try:
                return json.loads(result["raw_text"])
            except:
                pass
        
        # Fallback to basic extraction
        print(f"Warning: AI attribute extraction failed, using fallback")
        return _fallback_extraction(product_name)
        
    except Exception as e:
        print(f"Error in AI attribute extraction: {str(e)}")
        return _fallback_extraction(product_name)

def _fallback_extraction(product_name: str) -> Dict:
    """Fallback extraction using simple rules."""
    import re
    attributes = {}
    
    # Basic brand extraction
    known_brands = ["HP", "Dell", "Lenovo", "Apple", "Samsung", "Asus", "Acer", "MSI"]
    for brand in known_brands:
        if brand.lower() in product_name.lower():
            attributes["brand"] = brand
            break
    
    # Product type detection
    if any(word in product_name.lower() for word in ["laptop", "notebook"]):
        attributes["product_type"] = "Laptop"
    
    return attributes

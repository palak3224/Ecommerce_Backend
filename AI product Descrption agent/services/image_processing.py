from typing import Dict, List
from services.gemini_integration import analyze_image_with_gemini

def process_images(image_urls: List[str]) -> Dict:
    """
    Process product images using Gemini's vision API for comprehensive analysis.
    
    Args:
        image_urls: List of image URLs to analyze
    
    Returns:
        Dictionary with detailed image analysis, extracted text, and captions
    """
    detailed_analyses = []
    attribute_extractions = []
    captions = []
    
    for url in image_urls:
        try:
            # Get detailed analysis
            detailed = analyze_image_with_gemini(url, "detailed")
            detailed_analyses.append(detailed)
            
            # Get attribute extraction
            attributes = analyze_image_with_gemini(url, "attributes")
            attribute_extractions.append(attributes)
            
            # Get caption
            caption = analyze_image_with_gemini(url, "caption")
            captions.append(caption)
            
        except Exception as e:
            print(f"Error processing image {url}: {str(e)}")
            detailed_analyses.append(f"Error: {str(e)}")
            attribute_extractions.append("")
            captions.append("Unable to generate caption")
    
    return {
        "detailed_analysis": " | ".join(detailed_analyses),
        "extracted_attributes": " | ".join(attribute_extractions),
        "image_captions": " | ".join(captions)
    }

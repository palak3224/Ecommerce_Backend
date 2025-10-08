import requests
import json
import base64
from typing import Optional, Union, List
from io import BytesIO
from PIL import Image
from core.config import GEMINI_API_KEY, GEMINI_ENDPOINT, TEMPERATURE, MAX_TOKENS

def download_and_encode_image(image_url: str) -> tuple[str, str]:
    """Download image from URL and convert to base64."""
    response = requests.get(image_url, timeout=10)
    response.raise_for_status()
    
    # Detect mime type from content-type header
    content_type = response.headers.get('content-type', 'image/jpeg')
    
    # Convert to base64
    image_data = base64.b64encode(response.content).decode('utf-8')
    
    return image_data, content_type

def call_gemini(prompt: str, images: Optional[List[str]] = None, return_raw: bool = False) -> Union[dict, str]:
    """
    Call Gemini API with support for text and vision (multimodal) inputs.
    
    Args:
        prompt: The text prompt
        images: Optional list of image URLs to analyze
        return_raw: If True, returns raw text response instead of parsing JSON
    
    Returns:
        Parsed JSON dict or raw text response
    """
    url = f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}"
    
    # Build parts array with text and optional images
    parts = [{"text": prompt}]
    
    # Add images if provided
    if images:
        for image_url in images:
            try:
                image_data, mime_type = download_and_encode_image(image_url)
                parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_data
                    }
                })
            except Exception as e:
                print(f"Warning: Failed to process image {image_url}: {str(e)}")
    
    # Build payload according to Gemini API specification
    payload = {
        "contents": [{
            "parts": parts
        }],
        "generationConfig": {
            "temperature": TEMPERATURE,
            "maxOutputTokens": MAX_TOKENS,
        }
    }
    
    # Only set JSON response type if we're expecting JSON
    if not return_raw:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    
    headers = {"Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    
    response_data = resp.json()
    
    # Extract the generated text from Gemini's response structure
    try:
        generated_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
        
        if return_raw:
            return generated_text
        
        # Try to parse as JSON
        return json.loads(generated_text)
    except (KeyError, IndexError) as e:
        return {"error": f"Failed to extract response: {str(e)}", "raw_response": response_data}
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse JSON: {str(e)}", "raw_text": generated_text}

def analyze_image_with_gemini(image_url: str, analysis_type: str = "detailed") -> str:
    """
    Analyze an image using Gemini's vision capabilities with caching.
    
    Args:
        image_url: URL of the image to analyze
        analysis_type: Type of analysis - "detailed", "attributes", or "caption"
    
    Returns:
        Analysis text
    """
    # Try to get from cache first
    try:
        from core.cache import cache
        cached_analysis = cache.get_image_analysis(image_url, analysis_type)
        if cached_analysis:
            return cached_analysis
    except Exception as e:
        print(f"Cache check failed: {str(e)}")
    
    prompts = {
        "detailed": """Analyze this product image in detail. Describe:
1. The main product and its visible features
2. Colors, materials, and textures you can see
3. Any text or branding visible in the image
4. Product condition and quality indicators
5. Any technical specifications visible

Be specific and factual.""",
        
        "attributes": """Extract all visible product attributes from this image. List:
- Colors
- Materials
- Dimensions or size indicators
- Brand/model information
- Technical specifications
- Condition
- Style/design features

Output as a structured list.""",
        
        "caption": """Generate a concise, descriptive caption for this product image. 
Focus on the main product features visible in the image. Be specific and factual."""
    }
    
    prompt = prompts.get(analysis_type, prompts["detailed"])
    
    try:
        response = call_gemini(prompt, images=[image_url], return_raw=True)
        result = response if isinstance(response, str) else str(response)
        
        # Cache the result
        try:
            from core.cache import cache
            cache.set_image_analysis(image_url, analysis_type, result)
        except Exception as e:
            print(f"Cache set failed: {str(e)}")
        
        return result
    except Exception as e:
        return f"Error analyzing image: {str(e)}"

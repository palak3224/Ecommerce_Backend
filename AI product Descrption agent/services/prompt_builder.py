from typing import Dict
import json

def build_prompt(product_id: str, product_name: str, optional_prompt: str,
                 image_analysis: str, image_attributes: str, image_captions: str, 
                 extracted_attributes: Dict) -> str:
    """
    Build a comprehensive prompt for product description generation.
    
    Args:
        product_id: Product ID
        product_name: Name of the product
        optional_prompt: Optional tone/style guidance
        image_analysis: Detailed image analysis
        image_attributes: Attributes extracted from images
        image_captions: Image captions
        extracted_attributes: AI-extracted attributes
    
    Returns:
        Formatted prompt for Gemini
    """
    
    schema = {
        "title": "string (product title, enhanced if needed)",
        "short_description": "string (single line, 10-15 words max, catchy tagline)",
        "long_description": "string (3-4 detailed paragraphs, comprehensive and engaging)",
        "bullets": ["string (key features, 3-5 bullet points)"],
        "specs": {"key": "value (all technical specifications)"},
        "seo_keywords": ["string (relevant search keywords, 5-10 items)"],
        "tone": "string (the tone used)",
        "language": "string (language used)",
        "confidence": 0.0
    }

    prompt = f"""
SYSTEM: You are an expert e-commerce product copywriter AI. Your goal is to create compelling, accurate, and SEO-optimized product descriptions.

OUTPUT FORMAT: Valid JSON following this schema:
{json.dumps(schema, indent=2)}

INPUT DATA:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Product ID: {product_id}
Product Name: {product_name}
Desired Tone: {optional_prompt if optional_prompt else "professional and informative"}

IMAGE ANALYSIS:
{image_analysis}

VISIBLE ATTRIBUTES IN IMAGE:
{image_attributes}

IMAGE CAPTIONS:
{image_captions}

EXTRACTED ATTRIBUTES:
{json.dumps(extracted_attributes, indent=2)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INSTRUCTIONS:
1. **Title**: Create an enhanced product title (if original is too short/generic) or use the original if it's good

2. **Short Description**: Write a SINGLE LINE (10-15 words maximum)
   - This is a catchy tagline or quick hook
   - Should be punchy and memorable
   - Example: "Transform your space with this adorable panda-themed LED night light"
   - Keep it under 15 words!

3. **Long Description**: Write 3-4 DETAILED paragraphs (this is the main product description)
   - Paragraph 1: Opening hook with main benefit and what makes this product special
   - Paragraph 2: Detailed features, specifications, and how it works
   - Paragraph 3: Use cases, target audience, and practical benefits
   - Paragraph 4: Quality assurance, warranty info if visible, and compelling call-to-action
   - Make this comprehensive - 150-250 words total
   - Be engaging and thorough

4. **Bullets**: Create 3-5 concise bullet points highlighting key features
   - Each bullet should be specific and benefit-focused
   - Include technical specs where relevant

5. **Specs**: Include ALL technical specifications from the extracted attributes
   - Use the attributes provided as the foundation
   - Add any additional specs mentioned in image analysis
   - Format values cleanly (e.g., "12th Gen Intel Core i5" not just "i5")

6. **SEO Keywords**: Generate 5-10 relevant search terms people would use

7. **Tone**: Match the requested tone ({optional_prompt if optional_prompt else "professional and informative"})

8. **Language**: English

9. **Confidence**: Rate your confidence in the accuracy of the information (0.0-1.0)

CRITICAL RULES:
- Be factual - only use information from the input data
- Do NOT invent specifications or features not mentioned
- If something is uncertain, omit it or mark as "unknown"
- Use the extracted attributes in the specs section
- Make descriptions compelling but honest
- Focus on benefits, not just features

OUTPUT ONLY THE JSON OBJECT. NO OTHER TEXT.
"""
    return prompt.strip()

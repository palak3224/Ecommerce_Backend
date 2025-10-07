from services.image_processing import process_images
from services.attribute_extractor import extract_attributes
from services.prompt_builder import build_prompt
from services.gemini_integration import call_gemini
import json

def generate_product_description(product_id: str, product_name: str, image_urls: list, 
                                 optional_prompt: str = "professional and informative"):
    """
    Complete pipeline to generate AI-powered product descriptions.
    
    Args:
        product_id: Unique product identifier
        product_name: Name/title of the product
        image_urls: List of product image URLs
        optional_prompt: Desired tone/style for the description
    
    Returns:
        Dictionary with generated product description and metadata
    """
    print("=" * 80)
    print(f"🚀 Starting Product Description Generation for: {product_name}")
    print("=" * 80)
    
    # Step 1: Process Images with Gemini Vision
    print("\n📸 Step 1: Analyzing product images with AI vision...")
    image_data = process_images(image_urls)
    print("✅ Image analysis complete")
    
    # Step 2: Extract Attributes using AI
    print("\n🔍 Step 2: Extracting product attributes dynamically...")
    attributes = extract_attributes(
        product_name, 
        image_data["detailed_analysis"], 
        image_data["extracted_attributes"]
    )
    print(f"✅ Extracted {len(attributes)} attributes")
    print(f"   Attributes: {json.dumps(attributes, indent=2)}")
    
    # Step 3: Build Comprehensive Prompt
    print("\n📝 Step 3: Building optimized prompt...")
    prompt = build_prompt(
        product_id, 
        product_name, 
        optional_prompt,
        image_data["detailed_analysis"], 
        image_data["extracted_attributes"],
        image_data["image_captions"], 
        attributes
    )
    print("✅ Prompt ready")
    
    # Step 4: Generate Product Description with Gemini
    print("\n✨ Step 4: Generating product description with AI...")
    response = call_gemini(prompt)
    print("✅ Description generated successfully!")
    
    # Display results
    print("\n" + "=" * 80)
    print("📦 GENERATED PRODUCT DESCRIPTION")
    print("=" * 80)
    print(json.dumps(response, indent=2))
    
    return {
        "generated_content": response,
        "extracted_attributes": attributes,
        "image_analysis": image_data
    }

# Example Usage
if __name__ == "__main__":
    # Test input
    product_id = "1234"
    product_name = "Panda Night Light"
    image_urls = [
        "https://encrypted-tbn0.gstatic.com/shopping?q=tbn:ANd9GcTVecoAuIWroGMWb58VoVaSo6XaZ0SI9JRzLBBoIn46vbjODODjB72_xHlGZWPqrfE8phZfsbP5wpeOmqg4e_FZKiFQMtjJRwOj63Ztdom1"
    ]
    optional_prompt = "fun and casual"
    
    try:
        result = generate_product_description(
            product_id=product_id,
            product_name=product_name,
            image_urls=image_urls,
            optional_prompt=optional_prompt
        )
        
        print("\n" + "=" * 80)
        print("✅ PIPELINE COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

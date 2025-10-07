from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import json
from main import generate_product_description

app = FastAPI(
    title="AI Product Description Generator API",
    description="Generate compelling product descriptions using AI vision and text generation",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Models
class ProductDescriptionRequest(BaseModel):
    product_id: str = Field(..., description="Unique product identifier")
    product_name: str = Field(..., description="Name of the product")
    image_urls: List[str] = Field(..., description="List of product image URLs", min_items=1)
    tone: Optional[str] = Field("professional and informative", description="Desired tone/style (e.g., 'fun and casual', 'professional', 'luxury')")
    
    class Config:
        json_schema_extra = {
            "example": {
                "product_id": "1234",
                "product_name": "HP Victus 12th Gen Intel Core i5 Gaming Laptop",
                "image_urls": [
                    "https://example.com/product-image.jpg"
                ],
                "tone": "fun and casual"
            }
        }

# Response Models (matching your database schema)
class ProductMetaResponse(BaseModel):
    """Matches product_meta table schema"""
    product_id: str
    short_desc: str = Field(..., description="Short description (single line, catchy tagline)")
    full_desc: str = Field(..., description="Full description (3-4 detailed paragraphs)")
    meta_title: str = Field(..., description="SEO meta title")
    meta_desc: str = Field(..., description="SEO meta description")
    meta_keywords: str = Field(..., description="SEO keywords (comma-separated)")

class ProductDescriptionResponse(BaseModel):
    """Complete response with all generated content"""
    product_meta: ProductMetaResponse
    product_description: str = Field(..., description="Main product description (can be used for product.product_description)")
    title: str = Field(..., description="Enhanced product title")
    bullets: List[str] = Field(..., description="Key feature bullet points")
    specs: Dict[str, str] = Field(..., description="Product specifications/attributes")
    seo_keywords: List[str] = Field(..., description="SEO keywords as array")
    tone: str
    language: str
    confidence: float = Field(..., description="AI confidence score (0.0-1.0)")
    
    # Additional metadata
    extracted_attributes: Dict[str, str] = Field(..., description="Attributes extracted from images")
    image_analysis_summary: str = Field(..., description="Summary of image analysis")

class ErrorResponse(BaseModel):
    error: str
    details: Optional[str] = None

# API Endpoints
@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "AI Product Description Generator",
        "version": "1.0.0"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "service": "AI Product Description Generator",
        "endpoints": {
            "generate": "/api/generate-description",
            "docs": "/docs",
            "health": "/health"
        }
    }

@app.post(
    "/api/generate-description",
    response_model=ProductDescriptionResponse,
    tags=["Product Description"],
    summary="Generate AI-powered product description",
    description="Analyzes product images and generates comprehensive descriptions, SEO metadata, and specifications"
)
async def generate_description(request: ProductDescriptionRequest):
    """
    Generate complete product description using AI.
    
    Returns data structured to match your database schema:
    - product_meta: Maps to product_meta table (short_desc, full_desc, meta_title, meta_desc, meta_keywords)
    - product_description: Maps to product.product_description field
    - Additional metadata for frontend display
    """
    try:
        # Call the AI pipeline
        result = generate_product_description(
            product_id=request.product_id,
            product_name=request.product_name,
            image_urls=request.image_urls,
            optional_prompt=request.tone
        )
        
        # Extract generated content
        generated = result.get("generated_content", {})
        
        # Check for errors in generation
        if "error" in generated:
            raise HTTPException(
                status_code=500,
                detail=f"AI generation error: {generated.get('error', 'Unknown error')}"
            )
        
        # Get attributes and image analysis
        extracted_attrs = result.get("extracted_attributes", {})
        image_data = result.get("image_analysis", {})
        
        # Build response matching database schema
        
        # Short description: single line tagline
        short_desc = generated.get("short_description", "")
        
        # Full description: comprehensive 3-4 paragraphs
        full_desc = generated.get("long_description", "")
        
        # Meta title: use generated title or product name
        meta_title = generated.get("title", request.product_name)
        
        # Meta description: use short_description for SEO
        meta_desc = short_desc
        
        # Meta keywords: convert array to comma-separated string
        seo_keywords_array = generated.get("seo_keywords", [])
        meta_keywords = ", ".join(seo_keywords_array)
        
        # Product description: can use full_desc or a combination
        product_description = full_desc
        
        # Image analysis summary
        image_captions = image_data.get("image_captions", "")
        image_analysis_summary = image_captions[:200] + "..." if len(image_captions) > 200 else image_captions
        
        # Build the response
        response = ProductDescriptionResponse(
            product_meta=ProductMetaResponse(
                product_id=request.product_id,
                short_desc=short_desc,
                full_desc=full_desc,
                meta_title=meta_title,
                meta_desc=meta_desc,
                meta_keywords=meta_keywords
            ),
            product_description=product_description,
            title=generated.get("title", request.product_name),
            bullets=generated.get("bullets", []),
            specs=generated.get("specs", {}),
            seo_keywords=seo_keywords_array,
            tone=generated.get("tone", request.tone),
            language=generated.get("language", "English"),
            confidence=generated.get("confidence", 0.0),
            extracted_attributes=extracted_attrs,
            image_analysis_summary=image_analysis_summary
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error generating description: {error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate product description: {str(e)}"
        )

@app.post(
    "/api/generate-description-simple",
    tags=["Product Description"],
    summary="Generate description with simplified response",
    description="Returns only the essential fields for direct database insertion"
)
async def generate_description_simple(request: ProductDescriptionRequest):
    """
    Simplified endpoint that returns only database-ready fields.
    Perfect for direct insertion into your database.
    """
    try:
        # Get full response
        full_response = await generate_description(request)
        
        # Return simplified version matching database schema
        return {
            "product_id": request.product_id,
            
            # For product_meta table
            "product_meta": {
                "product_id": int(request.product_id) if request.product_id.isdigit() else request.product_id,
                "short_desc": full_response.product_meta.short_desc,
                "full_desc": full_response.product_meta.full_desc,
                "meta_title": full_response.product_meta.meta_title,
                "meta_desc": full_response.product_meta.meta_desc,
                "meta_keywords": full_response.product_meta.meta_keywords
            },
            
            # For product table
            "product_description": full_response.product_description,
            "enhanced_title": full_response.title,
            
            # Additional useful data
            "bullets": full_response.bullets,
            "specifications": full_response.specs
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate description: {str(e)}"
        )

# Run with: uvicorn api:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


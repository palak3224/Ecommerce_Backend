"""
Startup script for AI Product Description API
Run this file to start the FastAPI server
"""
import uvicorn

if __name__ == "__main__":
    print("=" * 80)
    print("🚀 Starting AI Product Description Generator API")
    print("=" * 80)
    print("\n📍 API will be available at:")
    print("   - Local: http://localhost:8000")
    print("   - Docs: http://localhost:8000/docs")
    print("   - ReDoc: http://localhost:8000/redoc")
    print("\n⚡ Press CTRL+C to stop the server\n")
    print("=" * 80)
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )


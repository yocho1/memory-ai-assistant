from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import os
import sys

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

print("🚀 Starting FastAPI app...")
print(f"📁 Current directory: {current_dir}")
print(f"📁 Files in directory: {os.listdir(current_dir)}")

# Try to import dependencies with better error handling
try:
    # Test basic imports first
    import sqlite3
    print("✅ sqlite3 imported")
    
    import google.generativeai as genai
    print("✅ google.generativeai imported")
    
    # Now try our custom modules
    from models import ChatRequest, ChatResponse
    print("✅ models imported")
    
    from config import settings
    print("✅ config imported")
    
    from memory_engine import MemoryEngine
    print("✅ memory_engine imported")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Trying alternative import approach...")
    
    # Alternative import approach
    import importlib.util
    import os
    
    # Import models
    models_path = os.path.join(current_dir, 'models.py')
    if os.path.exists(models_path):
        spec = importlib.util.spec_from_file_location("models", models_path)
        models = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(models)
        ChatRequest = models.ChatRequest
        ChatResponse = models.ChatResponse
        print("✅ models imported via alternative method")
    else:
        print("❌ models.py not found")
        raise

app = FastAPI(title="Memory AI Assistant with Gemini", version="1.0.0")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize memory engine
try:
    memory_engine = MemoryEngine(settings.DATABASE_URL, settings.GEMINI_API_KEY)
    print("✅ MemoryEngine initialized")
except Exception as e:
    print(f"❌ MemoryEngine initialization failed: {e}")
    memory_engine = None

@app.get("/")
async def root():
    return {"message": "Memory AI Assistant with Gemini API"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "timestamp": datetime.now(),
        "memory_engine_ready": memory_engine is not None
    }

@app.get("/test")
async def test_endpoint():
    try:
        if memory_engine:
            # Test database connection
            conn = memory_engine.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            
            return {
                "status": "success", 
                "message": "Backend is working!",
                "database_url": settings.DATABASE_URL,
                "gemini_configured": memory_engine.model is not None,
                "tables": [table[0] for table in tables],
                "files_in_app": os.listdir(current_dir)
            }
        else:
            return {
                "status": "partial_success",
                "message": "Backend is running but MemoryEngine not initialized",
                "database_url": settings.DATABASE_URL,
                "files_in_app": os.listdir(current_dir)
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}

# Simple chat endpoint for testing
@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        if not memory_engine:
            return JSONResponse(
                status_code=500,
                content={"error": "Memory engine not initialized"}
            )
        
        print(f"📨 Received: {request.message}")
        
        # Simple response for testing
        return {
            "response": f"Echo: {request.message}",
            "conversation_id": "test-conv-123",
            "memory_used": ["Test memory"],
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        print(f"❌ Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# CORS handlers
@app.options("/{rest_of_path:path}")
async def preflight_handler():
    return JSONResponse(
        content={"status": "ok"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.middleware("http")
async def add_cors_headers(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

print("✅ FastAPI app setup complete!")
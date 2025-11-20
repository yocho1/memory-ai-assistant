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
        print(f"🔍 Chat endpoint called")
        print(f"📨 User ID: {request.user_id}")
        print(f"💬 Message: {request.message}")
        print(f"🆔 Conversation ID: {request.conversation_id}")
        
        if not memory_engine:
            error_msg = "Memory engine not initialized"
            print(f"❌ {error_msg}")
            return JSONResponse(
                status_code=500,
                content={"error": error_msg}
            )
        
        # Test if we can access the memory engine methods
        print("🧠 Testing memory engine...")
        
        # Get relevant memories
        relevant_memories = memory_engine.search_memories(request.user_id, request.message)
        print(f"📚 Found {len(relevant_memories)} relevant memories")
        
        # Get conversation history
        conversation_history = memory_engine.get_conversation_history(request.user_id)
        print(f"💭 Found {len(conversation_history)} previous conversations")
        
        # Generate AI response
        print("🤖 Generating AI response...")
        ai_response = memory_engine.generate_response(
            request.message, 
            relevant_memories, 
            conversation_history
        )
        print(f"✅ AI response generated: {ai_response[:100]}...")
        
        # Store conversation
        messages = [
            {"role": "user", "content": request.message},
            {"role": "assistant", "content": ai_response}
        ]
        
        conversation_id = memory_engine.store_conversation(request.user_id, messages)
        print(f"💾 Stored conversation: {conversation_id}")
        
        # Store memory if needed
        if len(relevant_memories) == 0 or "remember" in request.message.lower():
            memory_engine.store_memory(
                request.user_id, 
                f"User discussed: {request.message}",
                {"type": "conversation_topic", "timestamp": datetime.now().isoformat()}
            )
            print(f"💾 Stored new memory")
        
        # Return response
        response_data = {
            "response": ai_response,
            "conversation_id": conversation_id,
            "memory_used": relevant_memories,
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"✅ Successfully returning response")
        return response_data
        
    except Exception as e:
        print(f"❌ Error in chat endpoint: {str(e)}")
        import traceback
        print(f"🔍 Full traceback: {traceback.format_exc()}")
        
        # Return a proper error response
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

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
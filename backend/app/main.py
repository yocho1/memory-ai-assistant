from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid
from datetime import datetime
from typing import List
import sys
import os

# Add the app directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

print(f"🔍 Current directory: {current_dir}")
print(f"📁 Files in app directory: {os.listdir(current_dir)}")

# Import from same directory - no dots
try:
    from models import ChatRequest, ChatResponse
    from memory_engine import MemoryEngine
    from config import settings
    print("✅ All imports successful!")
except ImportError as e:
    print(f"❌ Import error: {e}")
    # List available files to debug
    files = [f for f in os.listdir(current_dir) if f.endswith('.py')]
    print(f"📁 Available Python files: {files}")
    raise

app = FastAPI(title="Memory AI Assistant with Gemini", version="1.0.0")

# Vercel-compatible CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://memory-ai-assistant.vercel.app",
        "https://memory-ai-assistant-wpwf.vercel.app",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize memory engine with Gemini
memory_engine = MemoryEngine(settings.DATABASE_URL, settings.GEMINI_API_KEY)

@app.get("/")
async def root():
    return {"message": "Memory AI Assistant with Gemini API"}

# Test endpoint to verify everything works
@app.get("/test")
async def test_endpoint():
    try:
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
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        print(f"📨 Received message from user {request.user_id}: {request.message}")
        
        # Get relevant memories
        relevant_memories = memory_engine.search_memories(request.user_id, request.message)
        print(f"🧠 Found {len(relevant_memories)} relevant memories")
        
        # Get conversation history
        conversation_history = memory_engine.get_conversation_history(request.user_id)
        print(f"💬 Found {len(conversation_history)} previous conversations")
        
        # Generate AI response using Gemini
        ai_response = memory_engine.generate_response(
            request.message, 
            relevant_memories, 
            conversation_history
        )
        
        # Store new conversation
        messages = [
            {"role": "user", "content": request.message},
            {"role": "assistant", "content": ai_response}
        ]
        
        conversation_id = memory_engine.store_conversation(request.user_id, messages)
        print(f"💾 Stored conversation with ID: {conversation_id}")
        
        # Store important information as memory
        if len(relevant_memories) == 0 or "remember" in request.message.lower():
            memory_engine.store_memory(
                request.user_id, 
                f"User discussed: {request.message}",
                {"type": "conversation_topic", "timestamp": datetime.now().isoformat()}
            )
            print(f"💾 Stored new memory about: {request.message}")
        
        return ChatResponse(
            response=ai_response,
            conversation_id=conversation_id,
            memory_used=relevant_memories,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        print(f"❌ Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversations/{user_id}")
async def get_conversations(user_id: str):
    try:
        conversations = memory_engine.get_conversation_history(user_id)
        return JSONResponse(content={"conversations": conversations})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

# Handle OPTIONS requests for CORS preflight
@app.options("/{rest_of_path:path}")
async def preflight_handler():
    return JSONResponse(
        content={"status": "ok"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
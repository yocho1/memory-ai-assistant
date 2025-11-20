from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid
from datetime import datetime
from typing import List

from models import *
from memory_engine import MemoryEngine
from config import settings

app = FastAPI(title="Memory AI Assistant with Gemini", version="1.0.0")

# Enhanced CORS middleware - MUST be before route definitions
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://memory-ai-assistant.vercel.app",
        "https://memory-ai-assistant-wpwf.vercel.app",
        "http://localhost:3000",
        "http://localhost:8000",
        "*"  # Temporary for testing
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
)

# Initialize memory engine with Gemini
memory_engine = MemoryEngine(settings.DATABASE_URL, settings.GEMINI_API_KEY)

# Add explicit OPTIONS handler for preflight requests
@app.options("/chat")
async def options_chat():
    return JSONResponse(
        content={"status": "ok"},
        headers={
            "Access-Control-Allow-Origin": "https://memory-ai-assistant.vercel.app",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )

@app.options("/conversations/{user_id}")
async def options_conversations():
    return JSONResponse(
        content={"status": "ok"},
        headers={
            "Access-Control-Allow-Origin": "https://memory-ai-assistant.vercel.app",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )

@app.get("/")
async def root():
    return {"message": "Memory AI Assistant with Gemini API"}

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
        
        response = ChatResponse(
            response=ai_response,
            conversation_id=conversation_id,
            memory_used=relevant_memories,
            timestamp=datetime.now()
        )
        
        # Add CORS headers to response
        headers = {
            "Access-Control-Allow-Origin": "https://memory-ai-assistant.vercel.app",
            "Access-Control-Allow-Credentials": "true"
        }
        
        return JSONResponse(
            content=response.dict(),
            headers=headers
        )
        
    except Exception as e:
        print(f"❌ Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversations/{user_id}")
async def get_conversations(user_id: str):
    try:
        conversations = memory_engine.get_conversation_history(user_id)
        headers = {
            "Access-Control-Allow-Origin": "https://memory-ai-assistant.vercel.app",
            "Access-Control-Allow-Credentials": "true"
        }
        return JSONResponse(
            content={"conversations": conversations},
            headers=headers
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid
from datetime import datetime
from typing import List

# Correct imports - use relative imports within the app package
from .models import *
from .memory_engine import MemoryEngine
from .config import settings

app = FastAPI(title="Memory AI Assistant with Gemini", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Initialize memory engine with Gemini
memory_engine = MemoryEngine(settings.DATABASE_URL, settings.GEMINI_API_KEY)

@app.get("/")
async def root():
    return {"message": "Memory AI Assistant with Gemini API"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        print(f" Received message from user {request.user_id}: {request.message}")
        
        # Get relevant memories
        relevant_memories = memory_engine.search_memories(request.user_id, request.message)
        print(f" Found {len(relevant_memories)} relevant memories")
        
        # Get conversation history
        conversation_history = memory_engine.get_conversation_history(request.user_id)
        print(f" Found {len(conversation_history)} previous conversations")
        
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
        print(f" Stored conversation with ID: {conversation_id}")
        
        # Store important information as memory
        if len(relevant_memories) == 0 or "remember" in request.message.lower():
            memory_engine.store_memory(
                request.user_id, 
                f"User discussed: {request.message}",
                {"type": "conversation_topic", "timestamp": datetime.now().isoformat()}
            )
            print(f" Stored new memory about: {request.message}")
        
        return ChatResponse(
            response=ai_response,
            conversation_id=conversation_id,
            memory_used=relevant_memories,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        print(f" Error in chat endpoint: {e}")
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


# Add this at the VERY END of main.py
app = app  # This helps Vercel recognize the app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
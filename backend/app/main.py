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
    
    # Import the new VectorMemoryEngine instead of old MemoryEngine
    try:
        from memory_engine import VectorMemoryEngine
        print("✅ VectorMemoryEngine imported")
        MemoryEngine = VectorMemoryEngine  # Alias for compatibility
    except ImportError:
        # Fallback to old MemoryEngine if VectorMemoryEngine not available
        from memory_engine import MemoryEngine
        print("✅ MemoryEngine imported (fallback)")
    
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

# Initialize memory engine with better error handling
memory_engine = None
try:
    # Try to initialize VectorMemoryEngine first
    print("🔄 Initializing VectorMemoryEngine...")
    memory_engine = VectorMemoryEngine(settings.GEMINI_API_KEY)
    
    # Test if the engine is actually working
    if hasattr(memory_engine, 'memories'):
        print("✅ VectorMemoryEngine initialized successfully with ChromaDB!")
    else:
        print("⚠️ VectorMemoryEngine initialized but may have limited functionality")
        
except Exception as e:
    print(f"❌ VectorMemoryEngine initialization failed: {e}")
    
    # Fallback to old MemoryEngine
    try:
        print("🔄 Falling back to MemoryEngine...")
        from memory_engine import MemoryEngine
        memory_engine = MemoryEngine(settings.DATABASE_URL, settings.GEMINI_API_KEY)
        print("✅ MemoryEngine initialized (fallback mode)")
    except Exception as fallback_error:
        print(f"❌ MemoryEngine fallback also failed: {fallback_error}")
        memory_engine = None

@app.get("/")
async def root():
    return {"message": "Memory AI Assistant with Gemini API"}

@app.get("/health")
async def health_check():
    engine_type = "VectorMemoryEngine" if memory_engine and hasattr(memory_engine, 'memories') else "MemoryEngine" if memory_engine else "None"
    return {
        "status": "healthy", 
        "timestamp": datetime.now(),
        "memory_engine_ready": memory_engine is not None,
        "engine_type": engine_type,
        "gemini_configured": memory_engine.model is not None if memory_engine else False
    }

@app.get("/test")
async def test_endpoint():
    try:
        if memory_engine:
            # Test different aspects based on engine type
            test_results = {
                "status": "success", 
                "message": "Backend is working!",
                "gemini_configured": memory_engine.model is not None,
                "engine_type": "VectorMemoryEngine" if hasattr(memory_engine, 'memories') else "MemoryEngine",
                "files_in_app": os.listdir(current_dir)
            }
            
            # Test memory functionality
            try:
                if hasattr(memory_engine, 'get_user_stats'):
                    stats = memory_engine.get_user_stats("test_user")
                    test_results["memory_stats"] = stats
                else:
                    test_results["memory_stats"] = "Stats not available"
            except Exception as stats_error:
                test_results["memory_stats_error"] = str(stats_error)
            
            # Test vector DB if available
            if hasattr(memory_engine, 'memories'):
                try:
                    # Try to get collection info
                    collection_info = memory_engine.memories.get()
                    test_results["vector_db"] = {
                        "memory_count": len(collection_info['ids']) if collection_info['ids'] else 0,
                        "status": "connected"
                    }
                except Exception as vec_error:
                    test_results["vector_db"] = {"status": f"error: {vec_error}"}
            
            return test_results
        else:
            return {
                "status": "partial_success",
                "message": "Backend is running but MemoryEngine not initialized",
                "files_in_app": os.listdir(current_dir)
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/user/{user_id}/stats")
async def get_user_stats(user_id: str):
    """Get statistics for a specific user"""
    if not memory_engine:
        return {"error": "Memory engine not available"}
    
    try:
        if hasattr(memory_engine, 'get_user_stats'):
            stats = memory_engine.get_user_stats(user_id)
            return {
                "user_id": user_id,
                "stats": stats,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {"error": "User stats not available in current engine"}
    except Exception as e:
        return {"error": f"Failed to get user stats: {str(e)}"}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        print(f"🔍 Chat endpoint called")
        print(f"📨 User ID: {request.user_id}")
        print(f"💬 Message: {request.message}")
        print(f"🆔 Conversation ID: {request.conversation_id}")
        
        # If memory engine is not ready, provide a fallback response
        if not memory_engine:
            print("⚠️ Memory engine not available, using fallback response")
            
            fallback_response = f"I received your message: '{request.message}'. I'm currently running in basic mode without memory features. To enable full AI capabilities, please check the Gemini API configuration."
            
            return {
                "response": fallback_response,
                "conversation_id": f"fallback_{int(datetime.now().timestamp())}",
                "memory_used": [],
                "timestamp": datetime.now().isoformat(),
                "engine_type": "none"
            }
        
        # Try to use memory engine with error handling
        try:
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
            
            # Store memory - enhanced logic for better memory capture
            should_store_memory = (
                len(relevant_memories) == 0 or 
                "remember" in request.message.lower() or
                "name" in request.message.lower() or
                "my name" in request.message.lower() or
                "I am" in request.message.lower() or
                "I like" in request.message.lower() or
                "I love" in request.message.lower()
            )
            
            if should_store_memory:
                memory_content = f"User: {request.message}"
                memory_metadata = {
                    "type": "user_information",
                    "timestamp": datetime.now().isoformat(),
                    "category": "personal" if any(word in request.message.lower() for word in ['name', 'like', 'love', 'hate']) else "conversation"
                }
                memory_engine.store_memory(request.user_id, memory_content, memory_metadata)
                print(f"💾 Stored new memory: {memory_content[:50]}...")
            
            # Determine engine type for response
            engine_type = "vector" if hasattr(memory_engine, 'memories') else "sqlite"
            
            # Return response
            response_data = {
                "response": ai_response,
                "conversation_id": conversation_id,
                "memory_used": relevant_memories,
                "timestamp": datetime.now().isoformat(),
                "engine_type": engine_type,
                "memory_count": len(relevant_memories)
            }
            
            print(f"✅ Successfully returning response (using {engine_type} engine)")
            return response_data
            
        except Exception as memory_error:
            print(f"❌ Memory engine error: {memory_error}")
            import traceback
            print(f"🔍 Memory error traceback: {traceback.format_exc()}")
            
            # Fallback response when memory engine has issues
            fallback_response = f"I received your message: '{request.message}'. While my memory features are temporarily unavailable, I can still help with your question!"
            
            return {
                "response": fallback_response,
                "conversation_id": f"fallback_{int(datetime.now().timestamp())}",
                "memory_used": [],
                "timestamp": datetime.now().isoformat(),
                "engine_type": "error"
            }
        
    except Exception as e:
        print(f"❌ Error in chat endpoint: {str(e)}")
        import traceback
        print(f"🔍 Full traceback: {traceback.format_exc()}")
        
        # Always return a 200 response with error message in content
        return {
            "response": f"I encountered an error but received your message: '{request.message}'. Please try again.",
            "conversation_id": f"error_{int(datetime.now().timestamp())}",
            "memory_used": [],
            "timestamp": datetime.now().isoformat(),
            "engine_type": "error"
        }

@app.post("/memory/{user_id}")
async def store_memory_directly(user_id: str, content: str):
    """Endpoint to manually store a memory"""
    if not memory_engine:
        raise HTTPException(status_code=500, detail="Memory engine not available")
    
    try:
        memory_engine.store_memory(
            user_id, 
            content,
            {"type": "manual", "timestamp": datetime.now().isoformat()}
        )
        return {"status": "success", "message": "Memory stored successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store memory: {str(e)}")

@app.get("/memory/{user_id}")
async def get_user_memories(user_id: str, limit: int = 10):
    """Endpoint to get user memories"""
    if not memory_engine:
        raise HTTPException(status_code=500, detail="Memory engine not available")
    
    try:
        # This will only work with VectorMemoryEngine
        if hasattr(memory_engine, 'memories'):
            memories = memory_engine.memories.get(
                where={"user_id": user_id},
                limit=limit
            )
            return {
                "user_id": user_id,
                "memories": [
                    {
                        "content": doc,
                        "metadata": meta,
                        "id": mem_id
                    }
                    for doc, meta, mem_id in zip(
                        memories['documents'],
                        memories['metadatas'],
                        memories['ids']
                    )
                ]
            }
        else:
            return {"error": "Memory retrieval not available in current engine"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve memories: {str(e)}")

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

@app.on_event("startup")
async def startup_event():
    """Log startup information"""
    print("🎉 FastAPI app started successfully!")
    print(f"🧠 Memory Engine: {'✅ Ready' if memory_engine else '❌ Not available'}")
    if memory_engine:
        engine_type = "VectorMemoryEngine" if hasattr(memory_engine, 'memories') else "MemoryEngine"
        gemini_status = "✅ Configured" if memory_engine.model else "❌ Not configured"
        print(f"   Engine Type: {engine_type}")
        print(f"   Gemini AI: {gemini_status}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

print("✅ FastAPI app setup complete!")
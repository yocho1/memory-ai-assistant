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
    
    # Import the lightweight memory engine
    try:
        from memory_engine import LightweightMemoryEngine
        print("✅ LightweightMemoryEngine imported")
        MemoryEngine = LightweightMemoryEngine
    except ImportError:
        # Fallback to any available memory engine
        try:
            from memory_engine import MemoryEngine
            print("✅ MemoryEngine imported (fallback)")
        except ImportError:
            print("❌ No memory engine found")
            MemoryEngine = None
    
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
    print("🔄 Initializing LightweightMemoryEngine...")
    
    # Use the correct initialization for LightweightMemoryEngine
    if MemoryEngine and hasattr(MemoryEngine, '__name__') and 'Lightweight' in MemoryEngine.__name__:
        memory_engine = MemoryEngine(settings.GEMINI_API_KEY)
    else:
        # Fallback initialization
        memory_engine = MemoryEngine(settings.DATABASE_URL, settings.GEMINI_API_KEY) if MemoryEngine else None
    
    if memory_engine:
        print("✅ Memory engine initialized successfully!")
    else:
        print("❌ Memory engine initialization failed")
        
except Exception as e:
    print(f"❌ Memory engine initialization failed: {e}")
    memory_engine = None

@app.get("/")
async def root():
    return {"message": "Memory AI Assistant with Gemini API"}

@app.get("/health")
async def health_check():
    engine_type = "LightweightMemoryEngine" if memory_engine else "None"
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
            # Test memory functionality
            test_results = {
                "status": "success", 
                "message": "Backend is working!",
                "gemini_configured": memory_engine.model is not None,
                "engine_type": "LightweightMemoryEngine",
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
            
            # Enhanced memory storage logic
            should_store_memory = (
                len(relevant_memories) == 0 or 
                "remember" in request.message.lower() or
                "name" in request.message.lower() or
                "my name" in request.message.lower() or
                "i am" in request.message.lower() or
                "i like" in request.message.lower() or
                "i love" in request.message.lower() or
                "i work" in request.message.lower() or
                "i live" in request.message.lower()
            )
            
            if should_store_memory:
                # Use the memory engine's built-in extraction for better results
                # The memory engine will automatically extract and store important information
                print("💾 Memory engine will auto-extract important information")
            
            # Return response
            response_data = {
                "response": ai_response,
                "conversation_id": conversation_id,
                "memory_used": relevant_memories,
                "timestamp": datetime.now().isoformat(),
                "engine_type": "lightweight",
                "memory_count": len(relevant_memories)
            }
            
            print(f"✅ Successfully returning response")
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
    """Endpoint to get user memories (SQLite version)"""
    if not memory_engine:
        raise HTTPException(status_code=500, detail="Memory engine not available")
    
    try:
        # For LightweightMemoryEngine, we need to query SQLite directly
        if hasattr(memory_engine, 'get_connection'):
            conn = memory_engine.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, content, category, importance, created_at 
                FROM memories 
                WHERE user_id = ?
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
            ''', (user_id, limit))
            
            memories = []
            for row in cursor.fetchall():
                memories.append({
                    "id": row[0],
                    "content": row[1],
                    "category": row[2],
                    "importance": row[3],
                    "created_at": row[4]
                })
            
            conn.close()
            
            return {
                "user_id": user_id,
                "memories": memories,
                "total_count": len(memories)
            }
        else:
            return {"error": "Memory retrieval not available in current engine"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve memories: {str(e)}")

@app.get("/conversations/{user_id}")
async def get_user_conversations(user_id: str, limit: int = 5):
    """Get user's conversation history"""
    if not memory_engine:
        raise HTTPException(status_code=500, detail="Memory engine not available")
    
    try:
        conversations = memory_engine.get_conversation_history(user_id, limit)
        return {
            "user_id": user_id,
            "conversations": conversations,
            "total_count": len(conversations)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve conversations: {str(e)}")

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
        engine_type = "LightweightMemoryEngine"
        gemini_status = "✅ Configured" if memory_engine.model else "❌ Not configured"
        print(f"   Engine Type: {engine_type}")
        print(f"   Gemini AI: {gemini_status}")
        
        # Test basic functionality
        try:
            # Store a test memory to verify everything works
            memory_engine.store_memory(
                "system_test", 
                "System initialized successfully",
                {"type": "system", "category": "test"}
            )
            print("✅ System test memory stored successfully")
        except Exception as e:
            print(f"⚠️ System test memory failed: {e}")

# Add a simple test endpoint for quick verification
@app.get("/quick-test")
async def quick_test():
    """Quick test endpoint to verify basic functionality"""
    test_results = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "memory_engine": "ready" if memory_engine else "not_ready",
        "gemini": "configured" if memory_engine and memory_engine.model else "not_configured"
    }
    
    # Test memory storage and retrieval
    if memory_engine:
        try:
            # Store a test memory
            memory_engine.store_memory(
                "quick_test_user",
                "Test memory for quick verification",
                {"type": "test", "category": "verification"}
            )
            
            # Try to retrieve it
            memories = memory_engine.search_memories("quick_test_user", "test memory")
            test_results["memory_test"] = f"stored_and_retrieved_{len(memories)}_memories"
            
        except Exception as e:
            test_results["memory_test"] = f"error: {str(e)}"
    
    return test_results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

print("✅ FastAPI app setup complete!")
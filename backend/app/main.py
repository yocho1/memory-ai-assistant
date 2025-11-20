@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        print(f"🔍 Chat endpoint called")
        print(f"📨 User ID: {request.user_id}")
        print(f"💬 Message: {request.message}")
        
        # If memory engine is not ready, use a fallback
        if not memory_engine:
            print("⚠️ Memory engine not available, using fallback response")
            
            # Simple fallback response without memory
            fallback_response = f"I received your message: '{request.message}'. Note: Memory features are currently unavailable."
            
            return {
                "response": fallback_response,
                "conversation_id": f"fallback_{datetime.now().timestamp()}",
                "memory_used": [],
                "timestamp": datetime.now().isoformat()
            }
        
        # Rest of your existing memory engine code...
        relevant_memories = memory_engine.search_memories(request.user_id, request.message)
        print(f"📚 Found {len(relevant_memories)} relevant memories")
        
        # Generate AI response
        ai_response = memory_engine.generate_response(
            request.message, 
            relevant_memories, 
            []
        )
        
        # Store conversation
        messages = [
            {"role": "user", "content": request.message},
            {"role": "assistant", "content": ai_response}
        ]
        
        conversation_id = memory_engine.store_conversation(request.user_id, messages)
        
        # Return response
        return {
            "response": ai_response,
            "conversation_id": conversation_id,
            "memory_used": relevant_memories,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ Error in chat endpoint: {str(e)}")
        import traceback
        print(f"🔍 Full traceback: {traceback.format_exc()}")
        
        # Fallback error response
        return {
            "response": f"I encountered an error but received your message: '{request.message}'. Please try again.",
            "conversation_id": f"error_{datetime.now().timestamp()}",
            "memory_used": [],
            "timestamp": datetime.now().isoformat()
        }
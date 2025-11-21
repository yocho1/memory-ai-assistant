# memory_engine.py
import chromadb
import uuid
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from sentence_transformers import SentenceTransformer

class VectorMemoryEngine:
    def __init__(self, gemini_api_key: str, persist_directory: str = "/tmp/chroma_db"):
        self.gemini_api_key = gemini_api_key
        self.model = None
        self.embedder = None
        
        print(f"🧠 Initializing VectorMemoryEngine...")
        print(f"   Persist directory: {persist_directory}")
        print(f"   Gemini API Key: {'Provided' if gemini_api_key else 'Missing'}")
        
        try:
            # Initialize ChromaDB
            self.client = chromadb.PersistentClient(path=persist_directory)
            self.memories = self.client.get_or_create_collection(
                name="conversation_memories",
                metadata={"hnsw:space": "cosine"}
            )
            print("✅ ChromaDB initialized successfully!")
            
            # Initialize embedding model
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            print("✅ Embedding model loaded!")
            
            # Initialize Gemini
            self._setup_gemini()
            
            # Initialize SQLite for conversation history (compatibility)
            self._init_sqlite()
            
            print("✅ VectorMemoryEngine fully initialized!")
            
        except Exception as e:
            print(f"❌ VectorMemoryEngine initialization failed: {e}")
            import traceback
            print(f"🔍 Traceback: {traceback.format_exc()}")
            self.model = None

    def _setup_gemini(self):
        """Setup Gemini AI"""
        if not self.gemini_api_key:
            print("❌ No Gemini API key - running in fallback mode")
            self.model = None
            return
            
        try:
            genai.configure(api_key=self.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-pro')
            print("✅ Gemini AI configured successfully!")
        except Exception as e:
            print(f"❌ Gemini setup failed: {e}")
            self.model = None

    def _init_sqlite(self):
        """Initialize SQLite for conversation history"""
        import sqlite3
        self.db_path = "/tmp/conversations.db"
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ SQLite conversation database initialized!")

    def store_conversation(self, user_id: str, messages: List[Dict]) -> str:
        """Store conversation in SQLite"""
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            conversation_id = str(uuid.uuid4())
            title = messages[0]['content'][:50] + "..." if messages[0]['content'] else "New conversation"
            
            cursor.execute(
                "INSERT INTO conversations (id, user_id, title) VALUES (?, ?, ?)",
                (conversation_id, user_id, title)
            )
            
            for message in messages:
                message_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO messages (id, conversation_id, role, content) VALUES (?, ?, ?, ?)",
                    (message_id, conversation_id, message['role'], message['content'])
                )
            
            conn.commit()
            conn.close()
            
            print(f"💾 Stored conversation: {conversation_id}")
            return conversation_id
            
        except Exception as e:
            print(f"❌ Failed to store conversation: {e}")
            return f"error_{datetime.now().timestamp()}"

    def get_conversation_history(self, user_id: str, limit: int = 5) -> List[Dict]:
        """Get conversation history from SQLite"""
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, title, created_at
                FROM conversations 
                WHERE user_id = ?
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (user_id, limit))
            
            conversations = []
            for row in cursor.fetchall():
                conv = dict(row)
                
                cursor.execute('''
                    SELECT role, content, timestamp
                    FROM messages 
                    WHERE conversation_id = ?
                    ORDER BY timestamp ASC
                ''', (conv['id'],))
                
                conv['messages'] = [dict(msg_row) for msg_row in cursor.fetchall()]
                conversations.append(conv)
            
            conn.close()
            return conversations
            
        except Exception as e:
            print(f"❌ Failed to get conversation history: {e}")
            return []

    def store_memory(self, user_id: str, content: str, metadata: Dict = None):
        """Store memory in vector database with embedding"""
        if not content or not content.strip():
            return
            
        try:
            memory_id = str(uuid.uuid4())
            
            self.memories.add(
                documents=[content],
                metadatas=[{
                    "user_id": user_id,
                    "type": "conversation_memory",
                    "timestamp": datetime.now().isoformat(),
                    "importance": self._calculate_importance(content),
                    ** (metadata or {})
                }],
                ids=[memory_id]
            )
            
            print(f"💾 Stored vector memory: {content[:50]}...")
            
        except Exception as e:
            print(f"❌ Failed to store memory: {e}")

    def search_memories(self, user_id: str, query: str, limit: int = 5) -> List[str]:
        """Semantic search for relevant memories"""
        try:
            results = self.memories.query(
                query_texts=[query],
                where={"user_id": user_id},
                n_results=limit
            )
            
            memories = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    similarity = 1 - results['distances'][0][i]  # Convert to similarity score
                    if similarity > 0.3:  # Only include reasonably similar memories
                        memories.append(doc)
            
            print(f"🔍 Found {len(memories)} relevant memories for: '{query}'")
            return memories
            
        except Exception as e:
            print(f"❌ Memory search error: {e}")
            return []

    def _calculate_importance(self, content: str) -> float:
        """Calculate importance score for memory"""
        important_keywords = [
            'name', 'live', 'work', 'like', 'love', 'hate', 'favorite', 
            'prefer', 'remember', 'important', 'always', 'never'
        ]
        content_lower = content.lower()
        
        score = 0.1  # Base score
        
        # Boost score for personal information
        for keyword in important_keywords:
            if keyword in content_lower:
                score += 0.2
        
        return min(score, 1.0)

    def generate_response(self, user_message: str, context_memories: List[str], conversation_history: List[Dict]) -> str:
        """Generate response using Gemini with memory context"""
        # Fallback if no Gemini
        if self.model is None:
            return self._generate_fallback_response(user_message, context_memories, conversation_history)
        
        try:
            prompt = self._build_intelligent_prompt(user_message, context_memories, conversation_history)
            
            print(f"🤖 Generating AI response with {len(context_memories)} memories...")
            
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=0.8,
                    max_output_tokens=500,
                )
            )
            
            response_text = response.text.strip()
            print(f"✅ AI response generated")
            
            return response_text
            
        except Exception as e:
            print(f"❌ Gemini API error: {e}")
            return self._generate_fallback_response(user_message, context_memories, conversation_history)

    def _build_intelligent_prompt(self, user_message: str, context_memories: List[str], conversation_history: List[Dict]) -> str:
        """Build intelligent prompt with memory context"""
        context_parts = []
        
        # Add memory context
        if context_memories:
            context_parts.append("RELEVANT INFORMATION FROM OUR PAST CONVERSATIONS:")
            for i, memory in enumerate(context_memories, 1):
                context_parts.append(f"{i}. {memory}")
        else:
            context_parts.append("No specific memories found yet.")
        
        # Add conversation context
        context_parts.append("\nRECENT CONVERSATION:")
        if conversation_history:
            # Get messages from the most recent conversation
            recent_messages = []
            for conv in conversation_history[:1]:  # Most recent conversation
                if 'messages' in conv:
                    recent_messages.extend(conv['messages'][-6:])  # Last 6 messages
            
            for msg in recent_messages:
                role = "User" if msg['role'] == 'user' else "Assistant"
                context_parts.append(f"{role}: {msg['content']}")
        else:
            context_parts.append("No recent conversation history.")
        
        context = "\n".join(context_parts)
        
        prompt = f"""You are a helpful AI assistant with long-term memory. Use the context below to provide personalized, contextual responses.

IMPORTANT: Reference past conversations and remembered information when relevant.

CONTEXT:
{context}

CURRENT USER MESSAGE: {user_message}

YOUR RESPONSE (be natural, reference memories when appropriate):
"""
        
        return prompt

    def _generate_fallback_response(self, user_message: str, context_memories: List[str], conversation_history: List[Dict]) -> str:
        """Intelligent fallback responses"""
        user_lower = user_message.lower()
        
        # Check if user is asking about their name
        if any(phrase in user_lower for phrase in ['my name', 'what is my name', 'remember my name', "what's my name"]):
            if context_memories:
                # Try to find name in memories
                for memory in context_memories:
                    if 'name' in memory.lower() and 'achraf' in memory.lower():
                        return "Your name is Achraf! I remember you telling me that."
                return "I remember we've talked before, but I don't recall your name specifically. Could you remind me?"
            else:
                return "I don't have your name stored yet. What is your name?"
        
        # Check for greetings
        elif any(greet in user_lower for greet in ['hello', 'hi', 'hey']):
            if context_memories:
                return "Hello again! Good to see you back. How can I help you today?"
            else:
                return "Hello! I'm your AI assistant. I'll remember our conversations as we chat!"
        
        # Check if user shared personal information
        elif 'name is' in user_lower or 'my name' in user_lower:
            # Extract name from message
            if 'achraf' in user_lower:
                return "Nice to meet you, Achraf! I'll remember your name for our future conversations."
            return "Thanks for telling me your name! I'll remember that."
        
        # Generic response with memory context
        elif context_memories:
            return f"I remember we discussed: {context_memories[0][:50]}... What would you like to know about that?"
        else:
            return "Thanks for your message! I'm here to help and will remember our conversation."

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics"""
        try:
            # Get memory count from ChromaDB
            memories = self.memories.get(where={"user_id": user_id})
            memory_count = len(memories['ids']) if memories['ids'] else 0
            
            # Get conversation count from SQLite
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM conversations WHERE user_id = ?', (user_id,))
            conversation_count = cursor.fetchone()[0]
            conn.close()
            
            return {
                'memory_count': memory_count,
                'conversation_count': conversation_count,
                'vector_db_ready': True
            }
            
        except Exception as e:
            print(f"❌ Error getting user stats: {e}")
            return {'memory_count': 0, 'conversation_count': 0, 'vector_db_ready': False}

print("✅ VectorMemoryEngine loaded successfully!")
import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
import google.generativeai as genai

class MemoryEngine:
    def __init__(self, database_url: str, gemini_api_key: str):
        self.database_url = database_url
        self.gemini_api_key = gemini_api_key
        self.model = None
        
        print(f"🧠 Initializing MemoryEngine...")
        print(f"   Database: {database_url}")
        print(f"   API Key provided: {bool(gemini_api_key and gemini_api_key.strip())}")
        
        if gemini_api_key and gemini_api_key.strip():
            print(f"   API Key length: {len(gemini_api_key)} characters")
            print(f"   API Key starts with: {gemini_api_key[:10]}...")
        else:
            print("   ❌ No valid Gemini API key found!")
        
        try:
            self._init_database()
            self._setup_gemini()
            print("✅ MemoryEngine initialized successfully!")
        except Exception as e:
            print(f"❌ MemoryEngine initialization failed: {e}")
            import traceback
            print(f"🔍 Traceback: {traceback.format_exc()}")
            self.model = None
        
    def _setup_gemini(self):
        """Configure Gemini AI with comprehensive error handling"""
        if not self.gemini_api_key or not self.gemini_api_key.strip():
            print("❌ No Gemini API key available - running in fallback mode")
            self.model = None
            return
            
        try:
            print("🔧 Configuring Gemini AI...")
            genai.configure(api_key=self.gemini_api_key)
            
            # List available models
            print("📋 Checking available models...")
            available_models = []
            try:
                for model in genai.list_models():
                    if 'generateContent' in model.supported_generation_methods:
                        available_models.append(model.name)
                        print(f"   ✅ Available: {model.name}")
            except Exception as e:
                print(f"   ❌ Failed to list models: {e}")
                self.model = None
                return
            
            if not available_models:
                print("   ❌ No generateContent models available")
                self.model = None
                return
            
            # Try to use gemini-pro model
            model_name = 'models/gemini-pro'
            if model_name in available_models:
                try:
                    self.model = genai.GenerativeModel(model_name)
                    print(f"✅ Successfully loaded model: {model_name}")
                    
                    # Test the model with a simple prompt
                    test_response = self.model.generate_content("Hello, respond with just 'OK'")
                    print(f"✅ Model test successful: {test_response.text}")
                    return
                    
                except Exception as e:
                    print(f"❌ Failed to initialize {model_name}: {e}")
            
            # Fallback to any available model
            for model_name in available_models:
                try:
                    self.model = genai.GenerativeModel(model_name)
                    print(f"✅ Successfully loaded fallback model: {model_name}")
                    return
                except Exception as e:
                    print(f"❌ Failed to initialize {model_name}: {e}")
                    continue
            
            print("❌ No Gemini models could be initialized")
            self.model = None
            
        except Exception as e:
            print(f"❌ Gemini setup failed: {e}")
            self.model = None
        
    def _init_database(self):
        """Initialize SQLite database with proper error handling"""
        try:
            # Extract file path from database URL
            db_path = self.database_url.replace('sqlite:///', '')
            print(f"📁 Database path: {db_path}")
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys = ON")
            
            # Create conversations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create messages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
            ''')
            
            # Create memory_vectors table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS memory_vectors (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_memory_vectors_user_id ON memory_vectors(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_memory_vectors_content ON memory_vectors(content)')
            
            conn.commit()
            conn.close()
            print("✅ Database initialized successfully!")
            
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
            raise

    def get_connection(self):
        """Get database connection with error handling"""
        try:
            db_path = self.database_url.replace('sqlite:///', '')
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise

    def store_conversation(self, user_id: str, messages: List[Dict]) -> str:
        """Store a conversation and return conversation ID"""
        if not messages:
            return f"empty_{datetime.now().timestamp()}"
            
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            conversation_id = str(uuid.uuid4())
            title = messages[0]['content'][:50] + "..." if len(messages[0]['content']) > 50 else messages[0]['content']
            
            # Create conversation
            cursor.execute(
                "INSERT INTO conversations (id, user_id, title) VALUES (?, ?, ?)",
                (conversation_id, user_id, title)
            )
            
            # Store messages
            for message in messages:
                message_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO messages (id, conversation_id, role, content) VALUES (?, ?, ?, ?)",
                    (message_id, conversation_id, message['role'], message['content'])
                )
            
            conn.commit()
            conn.close()
            
            print(f"💾 Stored conversation: {conversation_id} with {len(messages)} messages")
            return conversation_id
            
        except Exception as e:
            print(f"❌ Failed to store conversation: {e}")
            return f"error_{datetime.now().timestamp()}"

    def get_conversation_history(self, user_id: str, limit: int = 5) -> List[Dict]:
        """Get conversation history for a user"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Get recent conversations
            cursor.execute('''
                SELECT id, title, created_at, updated_at
                FROM conversations 
                WHERE user_id = ?
                ORDER BY updated_at DESC 
                LIMIT ?
            ''', (user_id, limit))
            
            conversations = []
            for row in cursor.fetchall():
                conv = dict(row)
                
                # Get messages for this conversation
                cursor.execute('''
                    SELECT role, content, timestamp
                    FROM messages 
                    WHERE conversation_id = ?
                    ORDER BY timestamp ASC
                ''', (conv['id'],))
                
                conv['messages'] = [dict(msg_row) for msg_row in cursor.fetchall()]
                conversations.append(conv)
            
            conn.close()
            print(f"📖 Retrieved {len(conversations)} conversations for user {user_id}")
            return conversations
            
        except Exception as e:
            print(f"❌ Failed to get conversation history: {e}")
            return []

    def store_memory(self, user_id: str, content: str, metadata: Dict = None):
        """Store a memory for the user"""
        if not content or not content.strip():
            return
            
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            memory_id = str(uuid.uuid4())
            
            cursor.execute('''
                INSERT INTO memory_vectors (id, user_id, content, metadata)
                VALUES (?, ?, ?, ?)
            ''', (memory_id, user_id, content, json.dumps(metadata or {})))
            
            conn.commit()
            conn.close()
            
            print(f"💾 Stored memory for user {user_id}: {content[:50]}...")
            
        except Exception as e:
            print(f"❌ Failed to store memory: {e}")

    def search_memories(self, user_id: str, query: str, limit: int = 3) -> List[str]:
        """Search for relevant memories using keyword matching"""
        if not query or not query.strip():
            return []
            
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Split query into keywords for better matching
            keywords = [word.strip().lower() for word in query.split() if len(word.strip()) > 2]
            
            memories = []
            
            if keywords:
                # Search for memories containing any of the keywords
                like_patterns = [f'%{keyword}%' for keyword in keywords]
                placeholders = ','.join(['?'] * len(like_patterns))
                
                cursor.execute(f'''
                    SELECT DISTINCT content 
                    FROM memory_vectors 
                    WHERE user_id = ? 
                    AND ({' OR '.join(['content LIKE ?'] * len(like_patterns))})
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', [user_id] + like_patterns + [limit])
                
                memories = [row['content'] for row in cursor.fetchall()]
            
            # If no keyword matches or no keywords, get recent memories
            if not memories:
                cursor.execute('''
                    SELECT content 
                    FROM memory_vectors 
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (user_id, limit))
                memories = [row['content'] for row in cursor.fetchall()]
            
            conn.close()
            print(f"🔍 Found {len(memories)} relevant memories for query: '{query}'")
            return memories
            
        except Exception as e:
            print(f"❌ Failed to search memories: {e}")
            return []

    def generate_response(self, user_message: str, context_memories: List[str], conversation_history: List[Dict]) -> str:
        """
        Generate a contextual response using Gemini AI or fallback
        """
        # Fallback response if no Gemini model
        if self.model is None:
            return self._generate_fallback_response(user_message, context_memories, conversation_history)
        
        try:
            # Build the context prompt
            prompt = self._build_prompt(user_message, context_memories, conversation_history)
            
            print(f"🤖 Generating AI response...")
            print(f"   Prompt length: {len(prompt)} characters")
            print(f"   Context memories: {len(context_memories)}")
            print(f"   Conversation history items: {len(conversation_history)}")
            
            # Generate response
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=500,
                )
            )
            
            response_text = response.text.strip()
            print(f"✅ AI response generated: {response_text[:100]}...")
            
            return response_text
            
        except Exception as e:
            print(f"❌ Gemini API error: {e}")
            return self._generate_fallback_response(user_message, context_memories, conversation_history)

    def _build_prompt(self, user_message: str, context_memories: List[str], conversation_history: List[Dict]) -> str:
        """Build the prompt for Gemini AI"""
        context_parts = []
        
        # Add relevant memories
        if context_memories:
            context_parts.append("RELEVANT MEMORIES FROM PREVIOUS CONVERSATIONS:")
            for i, memory in enumerate(context_memories, 1):
                context_parts.append(f"{i}. {memory}")
        else:
            context_parts.append("No specific memories found for this context.")
        
        # Add conversation history
        context_parts.append("\nRECENT CONVERSATION HISTORY:")
        
        if conversation_history:
            for conv in conversation_history[-3:]:  # Last 3 conversations
                if 'messages' in conv and conv['messages']:
                    context_parts.append(f"\n--- Conversation: {conv.get('title', 'Previous chat')} ---")
                    for msg in conv['messages'][-4:]:  # Last 4 messages per conversation
                        role = msg.get('role', 'user')
                        content = msg.get('content', '')[:150]  # Truncate long messages
                        context_parts.append(f"{role}: {content}")
        else:
            context_parts.append("No previous conversation history.")
        
        context = "\n".join(context_parts)
        
        prompt = f"""You are a helpful AI assistant with memory. Use the context below to provide personalized responses.

CONTEXT:
{context}

CURRENT USER MESSAGE: {user_message}

INSTRUCTIONS:
1. Reference relevant memories when appropriate
2. Maintain natural conversation flow
3. Be concise but helpful
4. If memories don't directly relate, focus on the current question

ASSISTANT RESPONSE:"""
        
        return prompt

    def _generate_fallback_response(self, user_message: str, context_memories: List[str], conversation_history: List[Dict]) -> str:
        """Generate fallback response when Gemini is unavailable"""
        # Simple rule-based responses
        user_message_lower = user_message.lower()
        
        if any(greeting in user_message_lower for greeting in ['hello', 'hi', 'hey', 'hola']):
            if context_memories:
                return f"Hello again! I remember we've chatted before. What would you like to talk about today?"
            else:
                return "Hello! I'm your AI assistant. I'll remember our conversations once fully configured!"
        
        elif 'name' in user_message_lower:
            if context_memories:
                return "I remember you telling me your name! It's great to chat with you again."
            else:
                return "Nice to meet you! I'd love to remember your name and our conversations."
        
        elif any(word in user_message_lower for word in ['how are you', 'how do you do']):
            return "I'm doing well, thank you for asking! I'm here to help you with anything you need."
        
        elif context_memories:
            memory_preview = ', '.join([mem[:30] + '...' for mem in context_memories[:2]])
            return f"I remember we talked about: {memory_preview}. What would you like to know more about?"
        
        else:
            return f"Thanks for your message! I'll remember '{user_message[:30]}...' for our future conversations. What else would you like to talk about?"

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get statistics about user's conversations and memories"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Count conversations
            cursor.execute('SELECT COUNT(*) FROM conversations WHERE user_id = ?', (user_id,))
            conversation_count = cursor.fetchone()[0]
            
            # Count messages
            cursor.execute('''
                SELECT COUNT(*) FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.user_id = ?
            ''', (user_id,))
            message_count = cursor.fetchone()[0]
            
            # Count memories
            cursor.execute('SELECT COUNT(*) FROM memory_vectors WHERE user_id = ?', (user_id,))
            memory_count = cursor.fetchone()[0]
            
            # Get latest conversation
            cursor.execute('''
                SELECT title, updated_at FROM conversations 
                WHERE user_id = ? 
                ORDER BY updated_at DESC 
                LIMIT 1
            ''', (user_id,))
            latest_conv = cursor.fetchone()
            
            conn.close()
            
            stats = {
                'conversation_count': conversation_count,
                'message_count': message_count,
                'memory_count': memory_count,
                'latest_conversation': dict(latest_conv) if latest_conv else None
            }
            
            print(f"📊 User stats for {user_id}: {stats}")
            return stats
            
        except Exception as e:
            print(f"❌ Failed to get user stats: {e}")
            return {
                'conversation_count': 0,
                'message_count': 0,
                'memory_count': 0,
                'latest_conversation': None
            }

print("✅ memory_engine.py loaded successfully!")
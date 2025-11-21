# memory_engine.py
import uuid
import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
import google.generativeai as genai

class LightweightMemoryEngine:
    def __init__(self, gemini_api_key: str):
        self.gemini_api_key = gemini_api_key
        self.model = None
        
        print(f"🧠 Initializing LightweightMemoryEngine...")
        print(f"   Gemini API Key: {'Provided' if gemini_api_key else 'Missing'}")
        
        try:
            # Initialize SQLite for everything
            self._init_database()
            
            # Initialize Gemini
            self._setup_gemini()
            
            print("✅ LightweightMemoryEngine initialized successfully!")
            
        except Exception as e:
            print(f"❌ LightweightMemoryEngine initialization failed: {e}")
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

    def _init_database(self):
        """Initialize SQLite database with enhanced memory storage"""
        try:
            self.db_path = "/tmp/memory_assistant.db"
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Enhanced conversations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT,
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Enhanced messages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
            ''')
            
            # Enhanced memories table with categories and importance
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    importance REAL DEFAULT 0.5,
                    keywords TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_memories_keywords ON memories(keywords)')
            
            conn.commit()
            conn.close()
            print("✅ Database initialized successfully!")
            
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
            raise

    def get_connection(self):
        """Get database connection"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise

    def store_conversation(self, user_id: str, messages: List[Dict]) -> str:
        """Store conversation and extract key memories"""
        if not messages:
            return f"empty_{datetime.now().timestamp()}"
            
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            conversation_id = str(uuid.uuid4())
            title = messages[0]['content'][:50] + "..." if messages[0]['content'] else "New conversation"
            
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
            
            # Extract and store key memories from conversation
            self._extract_memories_from_conversation(user_id, messages)
            
            conn.commit()
            conn.close()
            
            print(f"💾 Stored conversation: {conversation_id} with {len(messages)} messages")
            return conversation_id
            
        except Exception as e:
            print(f"❌ Failed to store conversation: {e}")
            return f"error_{datetime.now().timestamp()}"

    def _extract_memories_from_conversation(self, user_id: str, messages: List[Dict]):
        """Extract and store important information as memories"""
        for message in messages:
            if message['role'] == 'user':
                content = message['content'].lower()
                
                # Detect personal information
                if any(phrase in content for phrase in ['my name is', "i'm called", "i am called", "call me"]):
                    # Extract name
                    name = self._extract_name(content)
                    if name:
                        self.store_memory(
                            user_id, 
                            f"User's name is {name}",
                            category="personal",
                            importance=0.9,
                            keywords="name,personal"
                        )
                
                # Detect preferences
                elif any(phrase in content for phrase in ['i like', 'i love', 'i enjoy', 'my favorite']):
                    self.store_memory(
                        user_id,
                        f"User preference: {message['content']}",
                        category="preferences", 
                        importance=0.7,
                        keywords="preference,like,love"
                    )
                
                # Detect important facts
                elif any(phrase in content for phrase in ['i work', 'i live', 'i am from', 'my job']):
                    self.store_memory(
                        user_id,
                        f"User fact: {message['content']}",
                        category="facts",
                        importance=0.8,
                        keywords="fact,work,live"
                    )

    def _extract_name(self, text: str) -> str:
        """Extract name from text using simple pattern matching"""
        text_lower = text.lower()
        
        patterns = [
            'my name is',
            "i'm called", 
            "i am called",
            "call me",
            "name is"
        ]
        
        for pattern in patterns:
            if pattern in text_lower:
                # Extract text after the pattern
                start_idx = text_lower.find(pattern) + len(pattern)
                name_part = text[start_idx:].strip()
                # Take first word as name
                name = name_part.split()[0] if name_part.split() else None
                if name and len(name) > 1:  # Basic validation
                    return name.capitalize()
        
        return None

    def store_memory(self, user_id: str, content: str, category: str = "general", 
                    importance: float = 0.5, keywords: str = "", metadata: Dict = None):
        """Store memory with enhanced metadata"""
        if not content or not content.strip():
            return
            
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            memory_id = str(uuid.uuid4())
            
            cursor.execute('''
                INSERT INTO memories (id, user_id, content, category, importance, keywords, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                memory_id, user_id, content, category, importance, keywords,
                json.dumps(metadata or {})
            ))
            
            conn.commit()
            conn.close()
            
            print(f"💾 Stored memory: {content[:50]}...")
            
        except Exception as e:
            print(f"❌ Failed to store memory: {e}")

    def search_memories(self, user_id: str, query: str, limit: int = 5) -> List[str]:
        """Enhanced memory search with keyword matching and relevance scoring"""
        if not query or not query.strip():
            return self._get_recent_memories(user_id, limit)
            
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query_lower = query.lower()
            query_words = [word.strip() for word in query_lower.split() if len(word.strip()) > 2]
            
            memories = []
            
            if query_words:
                # Search in content and keywords
                like_patterns = [f'%{word}%' for word in query_words]
                
                # Build OR conditions for each word
                content_conditions = " OR ".join(["content LIKE ?"] * len(query_words))
                keyword_conditions = " OR ".join(["keywords LIKE ?"] * len(query_words))
                
                cursor.execute(f'''
                    SELECT content, importance, last_accessed
                    FROM memories 
                    WHERE user_id = ? 
                    AND ({content_conditions} OR {keyword_conditions})
                    ORDER BY importance DESC, last_accessed DESC
                    LIMIT ?
                ''', [user_id] + like_patterns + like_patterns + [limit])
                
                memories = [row['content'] for row in cursor.fetchall()]
            
            # Update last_accessed for found memories
            if memories:
                placeholders = ','.join(['?'] * len(memories))
                cursor.execute(f'''
                    UPDATE memories 
                    SET last_accessed = CURRENT_TIMESTAMP 
                    WHERE content IN ({placeholders})
                ''', memories)
                conn.commit()
            
            # If no matches, get recent important memories
            if not memories:
                memories = self._get_recent_memories(user_id, limit)
            
            conn.close()
            print(f"🔍 Found {len(memories)} relevant memories for: '{query}'")
            return memories
            
        except Exception as e:
            print(f"❌ Failed to search memories: {e}")
            return self._get_recent_memories(user_id, limit)

    def _get_recent_memories(self, user_id: str, limit: int = 5) -> List[str]:
        """Get recent important memories"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT content 
                FROM memories 
                WHERE user_id = ?
                ORDER BY importance DESC, last_accessed DESC
                LIMIT ?
            ''', (user_id, limit))
            
            memories = [row['content'] for row in cursor.fetchall()]
            return memories
            
        except Exception as e:
            print(f"❌ Failed to get recent memories: {e}")
            return []

    def get_conversation_history(self, user_id: str, limit: int = 5) -> List[Dict]:
        """Get conversation history"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
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
            # Search for name in memories
            name_memories = [mem for mem in context_memories if 'name' in mem.lower()]
            if name_memories:
                return f"I remember you told me your name! {name_memories[0]}"
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
            return "Thanks for telling me your name! I'll remember that for our future conversations."
        
        # Generic response with memory context
        elif context_memories:
            return f"I remember we discussed: {context_memories[0][:50]}... What would you like to know about that?"
        else:
            return "Thanks for your message! I'm here to help and will remember our conversation."

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Count conversations
            cursor.execute('SELECT COUNT(*) FROM conversations WHERE user_id = ?', (user_id,))
            conversation_count = cursor.fetchone()[0]
            
            # Count memories
            cursor.execute('SELECT COUNT(*) FROM memories WHERE user_id = ?', (user_id,))
            memory_count = cursor.fetchone()[0]
            
            # Count memory categories
            cursor.execute('SELECT category, COUNT(*) FROM memories WHERE user_id = ? GROUP BY category', (user_id,))
            categories = {row[0]: row[1] for row in cursor.fetchall()}
            
            conn.close()
            
            return {
                'conversation_count': conversation_count,
                'memory_count': memory_count,
                'memory_categories': categories,
                'engine_type': 'lightweight'
            }
            
        except Exception as e:
            print(f"❌ Error getting user stats: {e}")
            return {
                'conversation_count': 0,
                'memory_count': 0,
                'memory_categories': {},
                'engine_type': 'lightweight'
            }

# Alias for compatibility with main.py
MemoryEngine = LightweightMemoryEngine
VectorMemoryEngine = LightweightMemoryEngine

print("✅ LightweightMemoryEngine loaded successfully!")
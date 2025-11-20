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
        self._init_database()
        self._setup_gemini()
        
    def _setup_gemini(self):
        """Configure Gemini AI with better error handling"""
        if not self.gemini_api_key:
            print(" No Gemini API key found!")
            self.model = None
            return
            
        try:
            genai.configure(api_key=self.gemini_api_key)
            print(" Gemini configured, checking available models...")
            
            # List available models to see what we have
            available_models = []
            for model in genai.list_models():
                if 'generateContent' in model.supported_generation_methods:
                    available_models.append(model.name)
                    print(f"    Available: {model.name}")
            
            # Try different model names
            model_attempts = [
                'models/gemini-pro',
                'gemini-pro',
                'models/gemini-1.0-pro',
                'gemini-1.0-pro'
            ]
            
            for model_name in model_attempts:
                try:
                    # Check if this model name matches any available model
                    matching_models = [m for m in available_models if model_name in m]
                    if matching_models:
                        actual_model_name = matching_models[0]
                        self.model = genai.GenerativeModel(actual_model_name)
                        print(f" Successfully loaded model: {actual_model_name}")
                        return
                except Exception as e:
                    print(f" Failed with {model_name}: {e}")
                    continue
            
            # If we get here, no model worked
            print(" No compatible Gemini model found")
            self.model = None
            
        except Exception as e:
            print(f" Gemini setup failed completely: {e}")
            self.model = None
        
    def _init_database(self):
        conn = sqlite3.connect(self.database_url.replace('sqlite:///', ''))
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memory_vectors (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print(" Database initialized successfully!")

    def get_connection(self):
        return sqlite3.connect(self.database_url.replace('sqlite:///', ''))

    def store_conversation(self, user_id: str, messages: List[Dict]) -> str:
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
        
        return conversation_id

    def get_conversation_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT c.id, c.title, c.updated_at, 
                   COUNT(m.id) as message_count
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            WHERE c.user_id = ?
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            LIMIT ?
        ''', (user_id, limit))
        
        conversations = [dict(row) for row in cursor.fetchall()]
        
        # Get messages for each conversation
        for conv in conversations:
            cursor.execute('''
                SELECT role, content, timestamp
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            ''', (conv['id'],))
            conv['messages'] = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return conversations

    def store_memory(self, user_id: str, content: str, metadata: Dict = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        memory_id = str(uuid.uuid4())
        
        cursor.execute('''
            INSERT INTO memory_vectors (id, user_id, content, metadata)
            VALUES (?, ?, ?, ?)
        ''', (memory_id, user_id, content, json.dumps(metadata or {})))
        
        conn.commit()
        conn.close()

    def search_memories(self, user_id: str, query: str, limit: int = 3) -> List[str]:
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Simple keyword-based search
        cursor.execute('''
            SELECT content 
            FROM memory_vectors 
            WHERE user_id = ? AND content LIKE ?
            LIMIT ?
        ''', (user_id, f'%{query}%', limit))
        
        memories = [dict(row)['content'] for row in cursor.fetchall()]
        
        # If no keyword matches, get recent memories
        if not memories:
            cursor.execute('''
                SELECT content 
                FROM memory_vectors 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, limit))
            memories = [dict(row)['content'] for row in cursor.fetchall()]
        
        conn.close()
        return memories

    def generate_response(self, user_message: str, context_memories: List[str], conversation_history: List[Dict]) -> str:
        """
        Generate a contextual response using Gemini AI with memory and conversation history.
        
        Args:
            user_message: The current user message
            context_memories: List of relevant memories from previous conversations
            conversation_history: List of conversation history dictionaries
            
        Returns:
            str: Generated response with contextual awareness
        """
        # If no Gemini model is available, use fallback
        if self.model is None:
            if context_memories:
                memory_preview = ', '.join([mem[:30] + '...' for mem in context_memories[:2]])
                return f" I remember we talked about: {memory_preview}. What would you like to know more about?"
            else:
                return " Hello! I'm your AI assistant. Tell me something about yourself so I can remember it for next time!"
        
        # Build comprehensive context from memories and history
        context_parts = []
        
        # Add relevant memories section
        if context_memories:
            context_parts.append(" Relevant memories from previous conversations:")
            for i, memory in enumerate(context_memories, 1):
                context_parts.append(f"{i}. {memory}")
        else:
            context_parts.append(" No specific memories found for this context.")
        
        # Add conversation history section
        context_parts.append("\n Recent conversation history:")
        
        if conversation_history:
            # Handle different conversation history structures
            # If it's a flat list of messages (old format)
            if all('role' in msg and 'content' in msg for msg in conversation_history):
                # Flat message list format - take last 6 messages
                recent_messages = conversation_history[-6:]
                for msg in recent_messages:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    # Truncate very long messages to avoid token limits
                    if len(content) > 200:
                        content = content[:200] + "..."
                    context_parts.append(f"{role}: {content}")
            
            # If it's a list of conversation objects with nested messages (new format)
            elif all('messages' in conv for conv in conversation_history):
                # Get last 3 conversations
                recent_conversations = conversation_history[-3:]
                
                for conv_idx, conv in enumerate(recent_conversations, 1):
                    if 'messages' in conv and conv['messages']:
                        # Add conversation header
                        title = conv.get('title', f'Conversation {conv_idx}')
                        context_parts.append(f"\n--- {title} ---")
                        
                        # Add last 4 messages from this conversation
                        recent_messages = conv['messages'][-4:]
                        for msg in recent_messages:
                            role = msg.get('role', 'user')
                            content = msg.get('content', '')
                            # Truncate very long messages to avoid token limits
                            if len(content) > 200:
                                content = content[:200] + "..."
                            context_parts.append(f"{role}: {content}")
            else:
                context_parts.append("No readable conversation history available.")
        else:
            context_parts.append("No previous conversation history available.")
        
        # Combine all context parts
        context = "\n".join(context_parts)
        
        # Construct the prompt with clear instructions
        prompt = f"""You are a helpful AI assistant with long-term memory. Use the following context to provide personalized, contextual responses.

IMPORTANT INSTRUCTIONS:
1. Reference relevant memories when appropriate
2. Maintain conversation continuity
3. Be natural and engaging
4. If memories don't directly relate, focus on the current question
5. Keep responses concise but helpful

{context}

Current user message: {user_message}

Assistant response:"""
        
        try:
            print(f" Sending prompt to Gemini...")
            print(f" Context length: {len(context)} characters")
            print(f" Current message: {user_message[:100]}{'...' if len(user_message) > 100 else ''}")
            
            response = self.model.generate_content(prompt)
            
            print(f" Successfully received response from Gemini")
            print(f" Response length: {len(response.text)} characters")
            
            return response.text
            
        except Exception as e:
            print(f" Gemini API error: {e}")
            
            # Enhanced fallback responses based on available context
            if context_memories:
                memory_summary = ', '.join([mem[:50] + '...' for mem in context_memories[:2]])
                return f" Based on our previous chats, I remember we discussed: {memory_summary}. What specific aspect would you like to explore further?"
            elif conversation_history:
                return " I recall our previous conversations! While I can't generate a detailed response right now, I'd love to continue our discussion. What would you like to talk about?"
            else:
                return " I'm here to help! Feel free to ask me anything, and I'll remember our conversation for next time. What's on your mind?"
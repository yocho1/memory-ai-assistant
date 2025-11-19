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
        """Configure Gemini AI"""
        genai.configure(api_key=self.gemini_api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
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
        # Build context from memories and history
        context = "Relevant memories from previous conversations:\n"
        for i, memory in enumerate(context_memories, 1):
            context += f"{i}. {memory}\n"
        
        context += "\nRecent conversation history:\n"
        for msg in conversation_history[-6:]:  # Last 6 messages
            context += f"{msg['role']}: {msg['content']}\n"
        
        prompt = f"""You are a helpful AI assistant with long-term memory. Use the following context to provide personalized responses.

{context}

Current user message: {user_message}

Assistant response:"""
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"I remember our previous conversations about: {', '.join(context_memories[:2]) if context_memories else 'various topics'}. How can I help you today? (Note: {str(e)})"
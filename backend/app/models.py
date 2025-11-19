from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class Message(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = None

class Conversation(BaseModel):
    id: str
    user_id: str
    title: str
    messages: List[Message]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ChatRequest(BaseModel):
    message: str
    user_id: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    memory_used: List[str]
    timestamp: datetime

class MemoryItem(BaseModel):
    id: str
    content: str
    metadata: Dict[str, Any]
    created_at: datetime
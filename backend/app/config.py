import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Use /tmp directory for SQLite on Vercel (writable)
    DATABASE_PATH = "/tmp/memory.db" if os.path.exists("/tmp") else "./memory.db"
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    def __init__(self):
        print(f"🔧 Configuration loaded:")
        print(f"   Database URL: {self.DATABASE_URL}")
        print(f"   Gemini API Key present: {'Yes' if self.GEMINI_API_KEY else 'No'}")
        if self.GEMINI_API_KEY:
            print(f"   API Key length: {len(self.GEMINI_API_KEY)} characters")
            print(f"   API Key starts with: {self.GEMINI_API_KEY[:10]}...")
    
settings = Settings()
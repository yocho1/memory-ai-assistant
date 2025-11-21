import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Use /tmp directory for SQLite on Vercel (writable)
    DATABASE_PATH = "/tmp/memory.db" if os.path.exists("/tmp") else "./memory.db"
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    def is_valid(self) -> bool:
        """Check if we have minimum required configuration"""
        return bool(self.GEMINI_API_KEY and self.GEMINI_API_KEY.strip())
    
settings = Settings()
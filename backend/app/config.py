import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Use /tmp directory for SQLite on Vercel (writable)
    DATABASE_PATH = "/tmp/memory.db" if os.path.exists("/tmp") else "./memory.db"
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
settings = Settings()
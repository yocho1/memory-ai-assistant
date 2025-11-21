import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    def __init__(self):
        print(f"🔧 Configuration loaded:")
        print(f"   Gemini API Key: {'Provided' if self.GEMINI_API_KEY else 'Missing'}")
        if self.GEMINI_API_KEY:
            print(f"   API Key starts with: {self.GEMINI_API_KEY[:10]}...")
    
settings = Settings()
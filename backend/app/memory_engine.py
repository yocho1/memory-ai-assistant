# In memory_engine.py, add better error handling
def __init__(self, database_url: str, api_key: str):
    self.database_url = database_url
    self.api_key = api_key
    
    try:
        # Initialize database
        self.init_database()
        
        # Initialize Gemini only if API key is provided
        if api_key and api_key != "":
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-pro')
            print("✅ Gemini model initialized successfully")
        else:
            self.model = None
            print("⚠️ Gemini API key not provided, running in limited mode")
            
    except Exception as e:
        print(f"❌ MemoryEngine initialization error: {e}")
        self.model = None

def generate_response(self, message: str, memories: list, history: list) -> str:
    # If no Gemini model, use fallback
    if not self.model:
        return f"I received: '{message}'. I found {len(memories)} relevant memories. Note: AI features are limited without API key."
    
    # Your existing Gemini code here...
    # ... rest of your generate_response method
import os
from dotenv import load_dotenv
load_dotenv()

GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
DB_NAME       = os.getenv("DB_NAME", "neurovista.db")
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
PORT          = int(os.getenv("PORT", 8000))

if not GROQ_API_KEY:
    print("⚠️  GROQ_API_KEY not set — AI will use fallback responses")

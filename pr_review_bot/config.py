import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Groq model to use — llama3 is fast and free
GROQ_MODEL = "llama3-70b-8192"

def validate_config():
    """Fail fast with clear error if env vars are missing"""
    missing = []

    if not GITHUB_TOKEN:
        missing.append("GITHUB_TOKEN")
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")

    if missing:
        raise EnvironmentError(
            f"\n❌ Missing required environment variables: {', '.join(missing)}\n"
            f"👉 Copy .env.example to .env and fill in your values.\n"
        )
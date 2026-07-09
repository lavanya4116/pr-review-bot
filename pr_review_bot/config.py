import os
from dotenv import load_dotenv
from pr_review_bot.exceptions import ConfigError

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Groq model to use — llama3 is fast and free
GROQ_MODEL = "llama-3.1-8b-instant"

def validate_config():
    """Fail fast with clear error if env vars are missing"""
    missing = []

    if not GITHUB_TOKEN:
        missing.append("GITHUB_TOKEN")
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")

    if missing:
        raise ConfigError(
            f"\n❌ Missing required environment variables: {', '.join(missing)}\n"
            f"👉 Copy .env.example to .env and fill in your values.\n"
        )
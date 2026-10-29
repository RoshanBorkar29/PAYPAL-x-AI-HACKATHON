"""Configuration management for Agent Wallet gateway."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Path resolution: support running from backend/ or repo root
BASE_DIR = Path(__file__).resolve().parent.parent  # .../backend
ROOT_DIR = BASE_DIR.parent                        # .../PAYPAL-x-AI-HACKATHON

# Load .env file from either backend/ or repo root
if (BASE_DIR / ".env").exists():
    load_dotenv(BASE_DIR / ".env")
elif (ROOT_DIR / ".env").exists():
    load_dotenv(ROOT_DIR / ".env")
else:
    load_dotenv()

# PayPal Sandbox Credentials
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")

# Groq LLM Settings
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Application & Database Settings
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "agent_wallet.db"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

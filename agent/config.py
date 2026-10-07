"""Agent settings: what comes from the environment and the limits that shape
its behaviour. Every other module reads its constants from here."""

import os

from dotenv import load_dotenv

load_dotenv()

# --- LLM server (OpenAI-compatible) ---
API_KEY = os.environ.get("API_KEY", "")
BASE_URL = os.environ.get("BASE_URL", "https://legion1.di.uoa.gr/v1")
MODEL = os.environ.get("MODEL", "llama3.1")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")

# --- IDE backend (inside Docker this is host.docker.internal, set in the Dockerfile) ---
IDE_BACKEND_URL = os.environ.get("IDE_BACKEND_URL", "http://localhost:3001/api")
IDE_TIMEOUT = 10

# --- Router ---
ROUTES = ["ide_action", "hyperai", "chitchat", "off_topic"]
FALLBACK_ROUTE = "chitchat"  # fail open: the main system prompt is the second line of defence
ROUTER_HISTORY_MESSAGES = 4

# --- Memory ---
MAX_HISTORY_MESSAGES = 10
MAX_SESSIONS = 100

# --- IDE actions ---
PLANNER_HISTORY_MESSAGES = 4
MAX_REPORTED_ERRORS = 8

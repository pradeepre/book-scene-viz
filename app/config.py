"""
Application configuration loaded from environment variables and .env.

All paths are relative to the project root so the app can run from any cwd
as long as imports resolve to this package.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (or cwd) before reading settings.
load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = ROOT / "data" / "uploads"       # Original page screenshots
GENERATED_DIR = ROOT / "data" / "generated"  # Saved scene images (PNG)
GALLERY_PATH = ROOT / "data" / "gallery.json"  # Simple local history store

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

# --- OpenAI settings ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Scene interpretation (text → JSON)
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")  # Image generation
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip() or None  # Optional proxy / Azure-style endpoint

# --- Image generation provider: openai | ollama ---
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "openai").strip().lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip()
OLLAMA_IMAGE_MODEL = os.getenv("OLLAMA_IMAGE_MODEL", "x/flux2-klein:4b")
OLLAMA_IMAGE_WIDTH = int(os.getenv("OLLAMA_IMAGE_WIDTH", "1024"))
OLLAMA_IMAGE_HEIGHT = int(os.getenv("OLLAMA_IMAGE_HEIGHT", "1024"))
_steps = os.getenv("OLLAMA_IMAGE_STEPS", "").strip()
OLLAMA_IMAGE_STEPS = int(_steps) if _steps else None

# Demo mode skips paid OpenAI calls and uses placeholder scene + image (no key required).
# Scene brief still uses OpenAI unless DEMO_MODE=1; only image step respects IMAGE_PROVIDER=ollama.
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1" or not OPENAI_API_KEY

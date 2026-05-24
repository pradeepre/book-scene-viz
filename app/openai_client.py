"""
Factory for a shared OpenAI SDK client.

Uses our custom httpx client so TLS/proxy settings from .env apply to every
chat and image request (important on corporate networks).
"""

from openai import OpenAI

from app.config import OPENAI_API_KEY, OPENAI_BASE_URL
from app.http_client import make_httpx_client


def get_openai_client() -> OpenAI:
    """Return a configured OpenAI client (one shared HTTP stack per call site)."""
    http_client = make_httpx_client(timeout=120.0)
    kwargs: dict = {"api_key": OPENAI_API_KEY, "http_client": http_client}
    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL
    return OpenAI(**kwargs)

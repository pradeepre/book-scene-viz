"""Shared HTTP client for OpenAI + image downloads (SSL / proxy friendly)."""

import os
from typing import Any

import httpx

try:
    import certifi
except ImportError:
    certifi = None  # type: ignore[assignment]


def ssl_verify_setting() -> bool | str:
    """
    Resolve TLS verification for httpx.

    Priority:
      OPENAI_SSL_VERIFY=0  → disable verification (corporate SSL inspection only)
      SSL_CERT_FILE        → path to custom CA bundle (preferred on corporate networks)
      default              → certifi bundle if available, else system default
    """
    raw = os.getenv("OPENAI_SSL_VERIFY", "1").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False

    cert_file = os.getenv("SSL_CERT_FILE", "").strip()
    if cert_file:
        return cert_file

    if certifi is not None:
        return certifi.where()

    return True


def make_httpx_client(**kwargs: Any) -> httpx.Client:
    """Build httpx client with project TLS settings (used by OpenAI SDK + URL downloads)."""
    verify = ssl_verify_setting()
    return httpx.Client(verify=verify, timeout=kwargs.pop("timeout", 120.0), **kwargs)


def format_api_error(exc: BaseException) -> str:
    """Turn SDK/network errors into actionable messages shown on the review page."""
    message = str(exc).strip() or exc.__class__.__name__

    if "CERTIFICATE_VERIFY_FAILED" in message or "certificate verify failed" in message:
        return (
            "TLS certificate verification failed when calling OpenAI. "
            "This often happens on corporate networks with SSL inspection.\n\n"
            "Try one of these (in .env), then restart the server:\n"
            "  1. SSL_CERT_FILE=/path/to/your-corporate-ca-bundle.pem\n"
            "  2. OPENAI_SSL_VERIFY=0   (disables verification — use only if you trust the network)\n\n"
            f"Technical detail: {message}"
        )

    if "Connection error" in message or isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return (
            "Could not reach the OpenAI API. Check internet access, VPN, firewall, or proxy settings.\n\n"
            f"Technical detail: {message}"
        )

    if "does not exist" in message and "model" in message.lower():
        return (
            f"{message}\n\n"
            "Your API key may not have access to that image model. "
            "In .env set OPENAI_IMAGE_MODEL=gpt-image-1 (recommended) or dall-e-2, then restart."
        )

    return message

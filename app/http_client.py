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


def _full_error_text(exc: BaseException) -> str:
    """Collect message from exception and its cause chain (OpenAI SDK often hides SSL detail)."""
    parts: list[str] = []
    current: BaseException | None = exc
    while current is not None:
        text = str(current).strip()
        if text and text not in parts:
            parts.append(text)
        current = current.__cause__
    return " ".join(parts) or exc.__class__.__name__


def format_api_error(exc: BaseException) -> str:
    """Turn SDK/network errors into actionable messages shown on the review page."""
    message = _full_error_text(exc)

    if "CERTIFICATE_VERIFY_FAILED" in message or "certificate verify failed" in message.lower():
        return (
            "TLS certificate verification failed when calling OpenAI. "
            "This often happens on corporate networks with SSL inspection (Zscaler, etc.).\n\n"
            "Add to .env and restart the server:\n"
            "  OPENAI_SSL_VERIFY=0\n\n"
            "Or use your company CA bundle (safer):\n"
            "  SSL_CERT_FILE=/path/to/corporate-ca-bundle.pem\n\n"
            f"Technical detail: {message}"
        )

    if "Connection error" in message or isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return (
            "Could not reach the OpenAI API. On corporate laptops this is usually fixed by "
            "adding OPENAI_SSL_VERIFY=0 to .env and restarting.\n\n"
            "Also check VPN, firewall, and proxy settings.\n\n"
            f"Technical detail: {message}"
        )

    if "does not exist" in message and "model" in message.lower():
        return (
            f"{message}\n\n"
            "Your API key may not have access to that image model. "
            "In .env set OPENAI_IMAGE_MODEL=gpt-image-1 (recommended) or dall-e-2, then restart."
        )

    return message

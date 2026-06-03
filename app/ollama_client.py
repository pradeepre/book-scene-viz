"""
Local image generation via Ollama (experimental image models).

Uses POST /api/generate with models such as x/flux2-klein or x/z-image-turbo.
See: https://github.com/ollama/ollama/blob/main/docs/api.md#image-generation-experimental

Note: Ollama image models currently require macOS with a recent Ollama version.
"""

import base64
from typing import Any

import httpx

from app.config import (
    OLLAMA_BASE_URL,
    OLLAMA_IMAGE_HEIGHT,
    OLLAMA_IMAGE_MODEL,
    OLLAMA_IMAGE_STEPS,
    OLLAMA_IMAGE_WIDTH,
)


def _ollama_http_client(**kwargs: Any) -> httpx.Client:
    """
    HTTP client for Ollama on localhost.

    trust_env=False avoids routing 127.0.0.1 through HTTP_PROXY — on corporate
    networks that sends local traffic to Zscaler and returns 403 Forbidden.
    """
    timeout = kwargs.pop("timeout", 15.0)
    return httpx.Client(timeout=timeout, trust_env=False, **kwargs)


def _proxy_blocked_response(response: httpx.Response) -> bool:
    """Detect corporate proxy (e.g. Zscaler) blocking localhost Ollama."""
    if response.status_code != 403:
        return False
    server = response.headers.get("server", "").lower()
    body = response.text[:500].lower()
    return "zscaler" in server or "zscaler" in body or "<!doctype html" in body


def check_ollama_health() -> dict[str, Any]:
    """Verify Ollama is running and the configured image model is available locally."""
    base = OLLAMA_BASE_URL.rstrip("/")
    try:
        with _ollama_http_client(timeout=15.0) as client:
            response = client.get(f"{base}/api/tags")
            if _proxy_blocked_response(response):
                return {
                    "ok": False,
                    "error": (
                        "Ollama request was blocked by a corporate HTTP proxy (403). "
                        "The app now bypasses proxy for Ollama — restart the server and try again.\n\n"
                        "If it persists, ensure Ollama is running: ollama serve"
                    ),
                }
            response.raise_for_status()
            tags = response.json()
    except httpx.ConnectError:
        return {
            "ok": False,
            "error": (
                f"Cannot connect to Ollama at {base}. "
                "Start it with: ollama serve"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}

    model_names = [m.get("name", "") for m in tags.get("models", [])]
    wanted = OLLAMA_IMAGE_MODEL
    base_name = wanted.split(":")[0]
    found = wanted in model_names or any(
        n == base_name or n.startswith(f"{base_name}:") for n in model_names
    )
    if not found:
        return {
            "ok": False,
            "error": (
                f"Model '{wanted}' not found locally. Installed: {model_names or '(none)'}\n"
                f"Pull it with: ollama pull {wanted}"
            ),
        }

    return {
        "ok": True,
        "message": f"Ollama ready — image model {wanted}",
        "models": model_names,
    }


def generate_image_ollama(prompt: str) -> bytes:
    """
    Generate a PNG/JPEG via Ollama and return raw image bytes.

    Final JSON response includes an ``image`` field with base64-encoded data.
    """
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload: dict[str, Any] = {
        "model": OLLAMA_IMAGE_MODEL,
        "prompt": prompt,
        "stream": False,
        "width": OLLAMA_IMAGE_WIDTH,
        "height": OLLAMA_IMAGE_HEIGHT,
    }
    if OLLAMA_IMAGE_STEPS is not None:
        payload["steps"] = OLLAMA_IMAGE_STEPS

    with _ollama_http_client(timeout=600.0) as client:
        response = client.post(url, json=payload)
        if _proxy_blocked_response(response):
            raise RuntimeError(
                "Ollama request was blocked by corporate HTTP proxy (403). "
                "Restart the app after updating — local Ollama calls bypass the proxy."
            )
        if response.status_code >= 400:
            detail = response.text[:500]
            raise RuntimeError(
                f"Ollama image generation failed ({response.status_code}): {detail}"
            )
        data = response.json()

    image_b64 = data.get("image")
    if not image_b64:
        raise RuntimeError(
            "Ollama returned no image data. "
            f"Is '{OLLAMA_IMAGE_MODEL}' an image model? "
            f"Try: ollama pull {OLLAMA_IMAGE_MODEL}"
        )

    return base64.b64decode(image_b64)

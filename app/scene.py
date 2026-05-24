"""
Literary scene interpretation and image generation via OpenAI.

Two-step pipeline:
  1. build_scene_brief — passage + book metadata → structured JSON + image_prompt
  2. generate_image    — image_prompt → PNG saved under data/generated/

GPT Image models (gpt-image-1) return base64; DALL·E models return temporary URLs.
"""

import base64
import json
import uuid
from pathlib import Path
from typing import Any

from app.config import (
    DEMO_MODE,
    GENERATED_DIR,
    OPENAI_IMAGE_MODEL,
    OPENAI_MODEL,
)
from app.http_client import make_httpx_client
from app.openai_client import get_openai_client

# Instructs the LLM to stay spoiler-safe and ground visuals in the passage only.
SCENE_SYSTEM_PROMPT = """You are a literary scene interpreter for fiction readers.
Given a book title, author, and a single passage from the book, produce a JSON object only.

Rules:
- Use ONLY details stated or clearly implied in the passage. Do not use outside plot knowledge.
- Do not spoil events beyond this passage.
- If something is ambiguous, list it in "ambiguities".
- image_prompt must be one paragraph, vivid, grounded, no text in the image, no logos.

Return valid JSON with keys:
setting, time_of_day, weather, characters_visible (array), objects (array),
mood, camera (wide|medium|close), ambiguities (array), image_prompt (string).
"""


def _demo_scene(passage: str, book_title: str, author: str) -> dict[str, Any]:
    """Fake scene brief when DEMO_MODE=1 or no API key (no OpenAI call)."""
    snippet = passage[:120] + ("…" if len(passage) > 120 else "")
    return {
        "setting": "As described in the scanned passage",
        "time_of_day": "unspecified",
        "weather": "unspecified",
        "characters_visible": [],
        "objects": [],
        "mood": "atmospheric",
        "camera": "medium",
        "ambiguities": ["Demo mode — connect OPENAI_API_KEY for real interpretation"],
        "image_prompt": (
            f"Literary illustration for {book_title} by {author}. "
            f"Grounded scene inspired by: {snippet}. "
            "Painterly, cinematic lighting, no text, no watermark."
        ),
    }


def build_scene_brief(
    passage: str,
    book_title: str,
    author: str,
) -> dict[str, Any]:
    """
    Ask the chat model to interpret the passage into structured scene metadata.

    response_format=json_object keeps output parseable for the result template.
    """
    if DEMO_MODE:
        return _demo_scene(passage, book_title, author)

    client = get_openai_client()
    user_content = json.dumps(
        {
            "book_title": book_title,
            "author": author,
            "passage": passage,
        },
        ensure_ascii=False,
    )
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SCENE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.4,  # Lower = stick closer to the passage wording
    )
    raw = response.choices[0].message.content or "{}"
    return json.loads(raw)


def _is_gpt_image_model(model: str) -> bool:
    """GPT Image models use a different API response shape than DALL·E."""
    return model.startswith("gpt-image") or model == "chatgpt-image-latest"


def _prompt_limit(model: str) -> int:
    """Each image model has a different max prompt length."""
    if _is_gpt_image_model(model):
        return 32000
    if model == "dall-e-2":
        return 1000
    return 4000  # dall-e-3


def generate_image(image_prompt: str) -> tuple[Path, str | None]:
    """
    Generate a scene PNG from the LLM's image_prompt.

    Returns (local_path, remote_url_or_none). GPT Image models have no URL.
    """
    filename = f"{uuid.uuid4().hex}.png"
    out_path = GENERATED_DIR / filename

    if DEMO_MODE:
        _write_placeholder_png(out_path, image_prompt)
        return out_path, None

    model = OPENAI_IMAGE_MODEL
    client = get_openai_client()
    prompt = image_prompt[: _prompt_limit(model)]

    if _is_gpt_image_model(model):
        # Newer keys default to gpt-image-1; response is base64, not a URL.
        result = client.images.generate(
            model=model,
            prompt=prompt,
            size="1024x1024",
            quality="medium",
            output_format="png",
            n=1,
        )
        b64_data = result.data[0].b64_json
        if not b64_data:
            raise RuntimeError("Image API returned no image data.")
        out_path.write_bytes(base64.b64decode(b64_data))
        return out_path, None

    # Legacy DALL·E path: API returns a short-lived HTTPS URL we must download.
    kwargs: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": "1024x1024",
        "n": 1,
    }
    if model == "dall-e-3":
        kwargs["quality"] = "standard"
    result = client.images.generate(**kwargs)
    url = result.data[0].url
    if not url:
        raise RuntimeError("Image API returned no URL.")

    with make_httpx_client(timeout=120.0) as http:
        response = http.get(url)
        response.raise_for_status()
        out_path.write_bytes(response.content)

    return out_path, url


def _write_placeholder_png(path: Path, label: str) -> None:
    """Draw a simple placeholder when demo mode avoids the Images API."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1024, 1024), color=(28, 32, 48))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(48, 48), (976, 976)], outline=(100, 120, 180), width=4)
    title = "Demo mode — set OPENAI_API_KEY"
    draw.text((80, 80), title, fill=(220, 225, 240))
    wrapped = _wrap(label, 52)
    y = 160
    for line in wrapped[:14]:
        draw.text((80, y), line, fill=(180, 190, 210))
        y += 36
    img.save(path, format="PNG")


def _wrap(text: str, width: int) -> list[str]:
    """Word-wrap prompt text onto the demo placeholder image."""
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word])
        if len(trial) <= width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines

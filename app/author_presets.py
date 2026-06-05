"""
Pre-loaded author style presets (bundled JSON, not user-entered in the UI).

Lookup by author name; if no preset matches, generation uses the default pipeline only.
"""

import json
import re
from functools import lru_cache
from typing import Any

from app.config import AUTHOR_STYLES_PATH


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


@lru_cache(maxsize=1)
def _load_catalog() -> list[dict[str, Any]]:
    if not AUTHOR_STYLES_PATH.exists():
        return []
    data = json.loads(AUTHOR_STYLES_PATH.read_text(encoding="utf-8"))
    return data.get("authors", [])


@lru_cache(maxsize=128)
def _alias_index() -> dict[str, str]:
    """Map normalized alias -> author preset id."""
    index: dict[str, str] = {}
    for entry in _load_catalog():
        preset_id = entry.get("id", "")
        for alias in entry.get("names", []):
            key = _normalize_name(alias)
            if key:
                index[key] = preset_id
    return index


def get_author_preset(author: str) -> dict[str, Any] | None:
    """
    Return a copy of the preset for this author name, or None for default generation.

    Matches exact normalized names and aliases from data/author_styles.json.
    """
    key = _normalize_name(author)
    if not key:
        return None

    preset_id = _alias_index().get(key)
    if not preset_id:
        return None

    for entry in _load_catalog():
        if entry.get("id") == preset_id:
            return {
                "preset_id": preset_id,
                "matched_name": author.strip(),
                "prose_style": entry.get("prose_style", ""),
                "narrative_tone": entry.get("narrative_tone", ""),
                "visual_aesthetic": entry.get("visual_aesthetic", ""),
                "recurring_motifs": list(entry.get("recurring_motifs") or []),
                "image_style_suffix": entry.get("image_style_suffix", ""),
            }
    return None


def apply_style_to_image_prompt(image_prompt: str, preset: dict[str, Any] | None) -> str:
    """Append preset art-direction when an author style is known."""
    if not preset:
        return image_prompt
    suffix = (preset.get("image_style_suffix") or "").strip()
    if not suffix:
        return image_prompt
    if suffix.lower() in image_prompt.lower():
        return image_prompt
    return f"{image_prompt.rstrip()} Visual style (author preset): {suffix}"


def list_preset_authors() -> list[str]:
    """Primary display names for docs / debugging."""
    return [entry.get("names", [""])[0] for entry in _load_catalog() if entry.get("names")]

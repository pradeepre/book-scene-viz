"""
Persist generated scenes to a local JSON file (MVP storage — no database).

Each entry links book metadata, the user-edited passage, LLM scene brief,
and filenames for the generated image (and optional upload screenshot).
"""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import GALLERY_PATH


def _load() -> list[dict[str, Any]]:
    if not GALLERY_PATH.exists():
        return []
    return json.loads(GALLERY_PATH.read_text(encoding="utf-8"))


def _save(entries: list[dict[str, Any]]) -> None:
    GALLERY_PATH.parent.mkdir(parents=True, exist_ok=True)
    GALLERY_PATH.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def add_entry(
    *,
    book_title: str,
    author: str,
    passage: str,
    scene_brief: dict[str, Any],
    image_filename: str,
    upload_filename: str | None = None,
) -> dict[str, Any]:
    """Append a new scene to the gallery (newest first) and return the record."""
    entry = {
        "id": uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "book_title": book_title,
        "author": author,
        "passage": passage,
        "scene_brief": scene_brief,
        "image_filename": image_filename,
        "upload_filename": upload_filename,
    }
    entries = _load()
    entries.insert(0, entry)  # Most recent at top for gallery UI
    _save(entries)
    return entry


def list_entries(limit: int = 50) -> list[dict[str, Any]]:
    return _load()[:limit]


def get_entry(entry_id: str) -> dict[str, Any] | None:
    for item in _load():
        if item["id"] == entry_id:
            return item
    return None

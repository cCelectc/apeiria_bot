"""JSON parsing helpers."""

from __future__ import annotations

from typing import Any


def safe_json_loads(text: str | None, default: Any = None) -> Any:
    """Safely parse JSON string, returning default on failure."""
    if not text:
        return default if default is not None else []

    import json

    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else []

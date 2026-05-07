"""Pure skill-selection response parsing."""

from __future__ import annotations

import json


def parse_skill_selection_response(
    content: str,
    *,
    known_names: set[str],
) -> list[str]:
    """Extract skill names from the model's JSON array response."""

    text = content.strip()

    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []

    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    selected_names: list[str] = []
    seen_names: set[str] = set()
    for name in parsed:
        if not isinstance(name, str):
            continue
        if name not in known_names or name in seen_names:
            continue
        selected_names.append(name)
        seen_names.add(name)
    return selected_names


__all__ = ["parse_skill_selection_response"]

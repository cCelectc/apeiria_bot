"""Pure skill-selection response parsing."""

from __future__ import annotations

import json


def parse_skill_selection_response(
    content: str,
    *,
    known_names: set[str],
) -> list[str]:
    """Extract skill names from the model's structured JSON response."""

    parsed = _parse_json_object(content)
    names = parsed.get("selected_names")
    if not isinstance(names, list):
        return []

    selected_names: list[str] = []
    seen_names: set[str] = set()
    for name in names:
        if not isinstance(name, str):
            continue
        if name not in known_names or name in seen_names:
            continue
        selected_names.append(name)
        seen_names.add(name)
    return selected_names


def _parse_json_object(content: str) -> dict[str, object]:
    text = content.strip()
    if not text:
        return {}
    if text.startswith("```"):
        text = _strip_code_fence(text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _strip_code_fence(content: str) -> str:
    lines = content.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


__all__ = ["parse_skill_selection_response"]

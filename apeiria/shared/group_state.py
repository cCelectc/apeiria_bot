"""Shared helpers for persisted group policy state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.shared.json_utils import safe_json_loads

if TYPE_CHECKING:
    from collections.abc import Iterable


def normalize_disabled_plugins(values: Iterable[object]) -> list[str]:
    """Normalize disabled plugin module names into a stable list."""
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        module = value.strip()
        if not module or module in seen:
            continue
        seen.add(module)
        normalized.append(module)
    normalized.sort()
    return normalized


def decode_disabled_plugins(raw: object | None) -> list[str]:
    """Decode persisted disabled plugin state from JSON text."""
    text = raw if isinstance(raw, str) else None
    values = safe_json_loads(text, default=[])
    if not isinstance(values, list):
        return []
    return normalize_disabled_plugins(values)

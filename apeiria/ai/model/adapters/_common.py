"""Shared coercion and text helpers used across model adapters."""

from __future__ import annotations

from typing import Any


def _coerce_str(extra: dict[str, Any] | None, key: str) -> str | None:
    if not extra:
        return None
    value = extra.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _coerce_int(extra: dict[str, Any] | None, key: str) -> int | None:
    if not extra:
        return None
    value = extra.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _coerce_float(extra: dict[str, Any] | None, key: str) -> float | None:
    if not extra:
        return None
    value = extra.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _coerce_custom_headers(
    extra: dict[str, Any] | None,
) -> dict[str, str] | None:
    if not extra:
        return None
    raw = extra.get("_custom_headers")
    if not isinstance(raw, dict):
        return None
    headers = {
        key.strip(): value.strip()
        for key, value in raw.items()
        if isinstance(key, str)
        and key.strip()
        and isinstance(value, str)
        and value.strip()
    }
    return headers or None


def _unsupported_part_text(kind: str) -> str:
    return f"[{kind} omitted: unsupported content representation]"

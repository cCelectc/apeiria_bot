"""Shared sanitization for persisted AI runtime diagnostics."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from typing import Any

MAX_DIAGNOSTIC_STRING_LENGTH = 200
MAX_DIAGNOSTIC_ITEMS = 20
MAX_DIAGNOSTIC_DEPTH = 6
REDACTED_DIAGNOSTIC_VALUE = "[redacted]"

_SECRET_KEY_PARTS = ("secret", "token", "api_key", "apikey", "password")
_BEARER_TOKEN_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"\b(api[_-]?key|token|secret|password)(\s*[:=]\s*)([^\s,;]+)",
    re.IGNORECASE,
)


def sanitize_runtime_diagnostics(
    payload: Mapping[str, Any] | None,
    *,
    max_string_length: int = MAX_DIAGNOSTIC_STRING_LENGTH,
    max_items: int = MAX_DIAGNOSTIC_ITEMS,
) -> dict[str, object]:
    """Return a JSON-safe, bounded, redacted diagnostic mapping."""

    if not payload:
        return {}
    sanitized = sanitize_runtime_diagnostic(
        dict(payload),
        max_string_length=max_string_length,
        max_items=max_items,
    )
    return sanitized if isinstance(sanitized, dict) else {}


def sanitize_runtime_diagnostic(  # noqa: PLR0911
    value: Any,
    *,
    key: str = "",
    max_string_length: int = MAX_DIAGNOSTIC_STRING_LENGTH,
    max_items: int = MAX_DIAGNOSTIC_ITEMS,
    _depth: int = 0,
) -> object:
    """Return a JSON-safe, bounded, redacted diagnostic value."""

    if _is_secret_key(key):
        return REDACTED_DIAGNOSTIC_VALUE
    if _depth >= MAX_DIAGNOSTIC_DEPTH:
        return _bounded_text(str(value), max_string_length)
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return _bounded_text(_redact_text(value), max_string_length)
    if is_dataclass(value) and not isinstance(value, type):
        return sanitize_runtime_diagnostic(
            asdict(value),
            key=key,
            max_string_length=max_string_length,
            max_items=max_items,
            _depth=_depth + 1,
        )
    if isinstance(value, Mapping):
        return {
            str(item_key): sanitize_runtime_diagnostic(
                item_value,
                key=str(item_key),
                max_string_length=max_string_length,
                max_items=max_items,
                _depth=_depth + 1,
            )
            for item_key, item_value in list(value.items())[:max_items]
        }
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [
            sanitize_runtime_diagnostic(
                item,
                key=key,
                max_string_length=max_string_length,
                max_items=max_items,
                _depth=_depth + 1,
            )
            for item in list(value)[:max_items]
        ]
    return _bounded_text(_redact_text(str(value)), max_string_length)


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(secret_part in lowered for secret_part in _SECRET_KEY_PARTS)


def _redact_text(value: str) -> str:
    redacted = _BEARER_TOKEN_RE.sub("Bearer [redacted]", value)
    return _SECRET_ASSIGNMENT_RE.sub(
        rf"\1\2{REDACTED_DIAGNOSTIC_VALUE}",
        redacted,
    )


def _bounded_text(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[:max_length]


__all__ = [
    "MAX_DIAGNOSTIC_ITEMS",
    "MAX_DIAGNOSTIC_STRING_LENGTH",
    "REDACTED_DIAGNOSTIC_VALUE",
    "sanitize_runtime_diagnostic",
    "sanitize_runtime_diagnostics",
]

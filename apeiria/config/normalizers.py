from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


def normalize_bool(value: object, *, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return fallback


def normalize_choice(
    value: object,
    *,
    allowed: set[str],
    fallback: str,
) -> str:
    if not isinstance(value, str):
        return fallback
    normalized = value.strip().lower()
    return normalized if normalized in allowed else fallback


def normalize_string(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    return value.strip()


def normalize_non_empty_string(value: object, *, fallback: str) -> str:
    text = normalize_string(value, fallback="")
    return text or fallback


def normalize_int(
    value: object,
    *,
    fallback: int,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    if isinstance(value, bool):
        return fallback
    if value is None:
        return fallback
    if not isinstance(value, (int, float, str)):
        return fallback
    try:
        result = int(value)
    except (TypeError, ValueError):
        return fallback
    if min_value is not None and result < min_value:
        result = min_value
    if max_value is not None and result > max_value:
        result = max_value
    return result


def normalize_float(value: object, *, fallback: float) -> float:
    if isinstance(value, bool):
        return fallback
    if value is None:
        return fallback
    if not isinstance(value, (int, float, str)):
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def validate_config(model: type[ModelT], data: dict[str, object]) -> ModelT:
    return model.model_validate(data)


def iter_raw_values(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(value)
    return (value,)


__all__ = [
    "iter_raw_values",
    "normalize_bool",
    "normalize_choice",
    "normalize_float",
    "normalize_int",
    "normalize_non_empty_string",
    "normalize_string",
    "validate_config",
]

"""Structured CLI output helpers."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

import click


def to_jsonable(value: Any) -> Any:
    """Convert dataclasses and paths into JSON-compatible values."""
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_jsonable(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    return value


def echo_json(payload: Any) -> None:
    """Emit one JSON payload."""
    click.echo(
        json.dumps(
            to_jsonable(payload),
            ensure_ascii=False,
            sort_keys=True,
        )
    )

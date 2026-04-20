"""Configuration field capability rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import HTTPException
from pydantic import BaseModel

if TYPE_CHECKING:
    from apeiria.plugins.metadata.api import RegisterConfig


@dataclass(frozen=True)
class TypeCapability:
    category: str
    editor: str
    editable: bool


def format_type_name(value: object | None) -> str | None:
    if value is None:
        return None
    return getattr(value, "__name__", str(value))


def get_field_capability(config: RegisterConfig) -> TypeCapability:
    if config.choices:
        capability = _capability_for_choice(config)
        if capability is not None:
            return capability

    capability = _capability_for_simple(config)
    if capability is not None:
        return capability

    capability = _capability_for_collection(config)
    if capability is not None:
        return capability

    return _readonly_capability("unsupported")


def normalize_value_for_response(
    config: RegisterConfig,
    value: object | None,
) -> object | None:
    if value is None:
        return None
    return _normalize_value_by_config(config, value)


def normalize_choices_for_response(values: list[object]) -> list[object]:
    return [_normalize_scalar_value(value) for value in values]


def normalize_choice_items_for_response(
    config: RegisterConfig,
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for value in config.choices:
        normalized = _normalize_scalar_value(value)
        key = str(normalized)
        items.append(
            {
                "title": config.choice_labels.get(key, key),
                "value": normalized,
            }
        )
    return items


def coerce_config_value(config: RegisterConfig, value: object) -> object:
    capability = get_field_capability(config)
    if not capability.editable:
        raise HTTPException(
            status_code=400,
            detail=f"field {config.key} is not editable",
        )

    if value is None:
        if config.allows_null:
            return None
        raise HTTPException(
            status_code=400,
            detail=f"field {config.key} does not allow null",
        )

    handlers = {
        "bool": _coerce_bool_value,
        "scalar": _coerce_scalar_value,
        "model": _coerce_model_value,
        "path": _coerce_string_value,
        "duration": _coerce_string_value,
        "text_like": _coerce_string_value,
        "sequence": _coerce_sequence_value,
        "mapping": _coerce_mapping_value,
    }
    handler = handlers.get(capability.category)
    if handler is None:
        raise HTTPException(
            status_code=400,
            detail=f"field {config.key} is not editable",
        )
    return handler(config, value)


def _editable_capability(category: str, editor: str) -> TypeCapability:
    return TypeCapability(category=category, editor=editor, editable=True)


def _readonly_capability(category: str) -> TypeCapability:
    return TypeCapability(category=category, editor="readonly", editable=False)


def _capability_for_choice(config: RegisterConfig) -> TypeCapability | None:
    if config.type is bool:
        return _editable_capability("bool", "select")
    if config.type in {str, int, float}:
        return _editable_capability("scalar", "select")
    return None


def _capability_for_simple(config: RegisterConfig) -> TypeCapability | None:
    capability: TypeCapability | None = None
    if config.type is bool:
        capability = _editable_capability("bool", "switch")
    elif config.type in {str, int, float}:
        capability = _editable_capability("scalar", "input")
    elif _is_model_type(config.type):
        capability = _editable_capability("model", "nested_object")
    elif config.type is Path:
        capability = _editable_capability("path", "input")
    elif config.type is timedelta:
        capability = _editable_capability("duration", "input")
    elif _supports_text_input(config.type):
        capability = _editable_capability("text_like", "input")
    return capability


def _capability_for_collection(config: RegisterConfig) -> TypeCapability | None:
    if config.type in {list, set}:
        return _capability_for_sequence(config)
    if config.type is dict:
        return _capability_for_mapping(config)
    return None


def _capability_for_sequence(config: RegisterConfig) -> TypeCapability:
    if config.item_schema is not None and _supports_nested_config(config.item_schema):
        return _editable_capability("sequence", "nested_sequence")
    if config.item_type not in {None, str}:
        return _readonly_capability("sequence")
    return _editable_capability("sequence", "chips")


def _capability_for_mapping(config: RegisterConfig) -> TypeCapability:
    if config.key_type is not str:
        return _readonly_capability("mapping")
    if config.value_schema is not None and _supports_nested_config(config.value_schema):
        return _editable_capability("mapping", "nested_mapping")
    return _readonly_capability("mapping")


def _supports_text_input(value: object) -> bool:
    if not isinstance(value, type):
        return False
    module_name = getattr(value, "__module__", "")
    return module_name.startswith("pydantic.networks")


def _is_model_type(value: object) -> bool:
    return isinstance(value, type) and issubclass(value, BaseModel)


def _supports_nested_config(config: RegisterConfig) -> bool:
    if config.choices:
        return _capability_for_choice(config) is not None
    if _capability_for_simple(config) is not None:
        return True
    if config.type in {list, set}:
        return config.item_schema is not None and _supports_nested_config(
            config.item_schema
        )
    if config.type is dict:
        return (
            config.key_type is str
            and config.value_schema is not None
            and _supports_nested_config(config.value_schema)
        )
    return False


def _normalize_scalar_value(value: object) -> object:
    if isinstance(value, Path | timedelta):
        return str(value)
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python")
    if isinstance(value, bool | int | float | str):
        return value
    return str(value)


def _normalize_value_by_config(
    config: RegisterConfig,
    value: object,
) -> object:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")

    if config.type in {list, set} and isinstance(value, list | set | tuple):
        item_config = config.item_schema
        if item_config is None:
            return [_normalize_scalar_value(item) for item in value]
        return [_normalize_value_by_config(item_config, item) for item in value]

    if config.type is dict and isinstance(value, dict):
        value_config = config.value_schema
        return {
            str(key): (
                _normalize_value_by_config(value_config, item)
                if value_config is not None
                else _normalize_json_compatible_value(item)
            )
            for key, item in value.items()
        }

    if _is_model_type(config.type):
        if not isinstance(value, dict):
            return _normalize_json_compatible_value(value)
        next_value: dict[str, object | None] = {}
        for field in config.fields:
            if field.key not in value:
                continue
            next_value[field.key] = _normalize_value_by_config(field, value[field.key])
        return next_value

    return _normalize_scalar_value(value)


def _normalize_json_compatible_value(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _normalize_json_compatible_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list | set | tuple):
        return [_normalize_json_compatible_value(item) for item in value]
    return _normalize_scalar_value(value)


def _coerce_bool_value(config: RegisterConfig, value: object) -> bool:
    if isinstance(value, bool):
        return value
    raise HTTPException(status_code=400, detail=f"field {config.key} expects bool")


def _coerce_scalar_value(config: RegisterConfig, value: object) -> object:
    expected = config.type
    if expected is str:
        return _coerce_string_value(config, value)
    if expected is int and isinstance(value, int) and not isinstance(value, bool):
        return value
    if (
        expected is float
        and isinstance(value, int | float)
        and not isinstance(
            value,
            bool,
        )
    ):
        return float(value)
    raise HTTPException(
        status_code=400,
        detail=f"field {config.key} expects {format_type_name(expected)}",
    )


def _coerce_string_value(config: RegisterConfig, value: object) -> str:
    if isinstance(value, str):
        return value
    raise HTTPException(status_code=400, detail=f"field {config.key} expects string")


def _coerce_model_value(config: RegisterConfig, value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise HTTPException(
            status_code=400,
            detail=f"field {config.key} expects object",
        )

    normalized: dict[str, object] = {}
    for field in config.fields:
        if field.key not in value:
            continue
        normalized[field.key] = coerce_config_value(field, value[field.key])
    return normalized


def _coerce_sequence_value(config: RegisterConfig, value: object) -> list[object]:
    if not isinstance(value, list):
        raise HTTPException(
            status_code=400,
            detail=f"field {config.key} expects list",
        )
    item_config = config.item_schema
    if item_config is None:
        if config.item_type not in {None, str}:
            raise HTTPException(
                status_code=400,
                detail=f"field {config.key} is not editable",
            )
        if not all(isinstance(item, str) for item in value):
            raise HTTPException(
                status_code=400,
                detail=f"field {config.key} expects string items",
            )
        return value
    return [coerce_config_value(item_config, item) for item in value]


def _coerce_mapping_value(
    config: RegisterConfig,
    value: object,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise HTTPException(
            status_code=400,
            detail=f"field {config.key} expects object",
        )
    if config.key_type is not str or config.value_schema is None:
        raise HTTPException(
            status_code=400,
            detail=f"field {config.key} is not editable",
        )
    normalized: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise HTTPException(
                status_code=400,
                detail=f"field {config.key} expects string keys",
            )
        normalized[key] = coerce_config_value(config.value_schema, item)
    return normalized

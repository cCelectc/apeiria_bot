from __future__ import annotations

import typing
from datetime import timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Literal, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel, SecretBytes, SecretStr

from apeiria.config.schema import (
    AnyField,
    ArrayField,
    FieldNode,
    MapField,
    ObjectField,
    PrimitiveField,
)

_TYPE_MAP: dict[object, str] = {
    str: "str",
    int: "int",
    float: "float",
    bool: "bool",
    Decimal: "float",
    UUID: "str",
    Path: "str",
    timedelta: "str",
}

_SECRET_TYPES: tuple[type, ...] = (SecretStr, SecretBytes)

_STRING_LIKE_TYPES: tuple[type, ...] = (UUID, Path, timedelta)


def _try_import_ipaddress_types() -> dict[type, str]:
    result: dict[type, str] = {}
    try:
        from ipaddress import IPv4Address, IPv6Address, IPvAnyAddress

        result[IPv4Address] = "str"
        result[IPv6Address] = "str"
        result[IPvAnyAddress] = "str"
    except ImportError:
        pass
    try:
        from pydantic.networks import AnyUrl, FileUrl, HttpUrl

        result[AnyUrl] = "str"
        result[FileUrl] = "str"
        result[HttpUrl] = "str"
    except ImportError:
        pass
    return result


_TYPE_MAP.update(_try_import_ipaddress_types())


def _get_pydantic_type(field_info: Any) -> type:
    return field_info.annotation


def _is_optional(annotation: type) -> bool:
    origin = get_origin(annotation)
    if origin is typing.Union:
        args = get_args(annotation)
        return type(None) in args
    return False


def _unwrap_optional(annotation: type) -> type:
    origin = get_origin(annotation)
    if origin is typing.Union:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0]
        return annotation
    return annotation


def _infer_primitive_type(annotation: type) -> str:
    origin = get_origin(annotation)
    if origin is Literal:
        return "literal"
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return "enum"
    return _TYPE_MAP.get(annotation, "str")


def _extract_choices(annotation: type) -> list[dict[str, str]] | None:
    origin = get_origin(annotation)
    if origin is Literal:
        args = get_args(annotation)
        return [{"value": str(a), "label": str(a)} for a in args]
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return [{"value": member.value, "label": member.name} for member in annotation]
    return None


class _FakeFieldInfo:
    def __init__(self, annotation: type) -> None:
        self.annotation = annotation
        self.description = None
        self.title = None

    def is_required(self) -> bool:
        return True

    def get_default(self, *, call_default_factory: Any = False) -> Any:  # noqa: ARG002
        return None


def _make_fake_field_info(annotation: type) -> _FakeFieldInfo:
    return _FakeFieldInfo(annotation)


_JSON_SAFE_TYPES = (str, int, float, bool, list, dict, type(None))


def _make_json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, _JSON_SAFE_TYPES):
        return value
    return str(value)


def _field_default_to_dict(default_val: Any) -> Any:
    if default_val is None:
        return None
    if isinstance(default_val, BaseModel):
        try:
            return default_val.model_dump()
        except (AttributeError, TypeError):
            return None
    return default_val


def _reflect_field(field_name: str, field_info: Any) -> FieldNode:
    annotation = _get_pydantic_type(field_info)
    if annotation is None:
        annotation = str

    is_required = field_info.is_required()
    description = field_info.description or ""
    title = field_info.title or ""

    base_kwargs: dict[str, Any] = {
        "key": field_name,
        "label": title or field_name,
        "description": description,
    }

    is_secret = isinstance(annotation, type) and issubclass(annotation, _SECRET_TYPES)

    optional = _is_optional(annotation)
    if optional:
        annotation = _unwrap_optional(annotation)

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        children = reflect_model(annotation)
        raw_default = field_info.get_default(call_default_factory=True)
        return ObjectField(
            children=children,
            default=_field_default_to_dict(raw_default),
            **base_kwargs,
        )

    origin = get_origin(annotation)
    if origin in (list, set):
        args = get_args(annotation)
        item_type = args[0] if args else str
        item_schema = _reflect_field("", _make_fake_field_info(item_type))
        return ArrayField(item_schema=item_schema, **base_kwargs)

    if origin is dict:
        args = get_args(annotation)
        value_type = args[1] if len(args) > 1 else str
        value_schema = _reflect_field("", _make_fake_field_info(value_type))
        return MapField(value_schema=value_schema, **base_kwargs)

    ptype = _infer_primitive_type(annotation)
    choices = _extract_choices(annotation)
    default_val = field_info.get_default(call_default_factory=True)

    return PrimitiveField(
        type=ptype,
        default=_make_json_safe(default_val),
        required=is_required and not optional,
        secret=is_secret,
        choices=choices or None,
        **base_kwargs,
    )


def reflect_model(model_cls: type[BaseModel]) -> list[FieldNode]:
    fields: list[FieldNode] = []
    for field_name, field_info in model_cls.model_fields.items():
        try:
            node = _reflect_field(field_name, field_info)
            fields.append(node)
        except (TypeError, ValueError, KeyError):
            fields.append(
                AnyField(
                    key=field_name,
                    label=field_name,
                    description=field_info.description
                    or f"Type: {field_info.annotation}",
                )
            )
    return fields

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class FieldNode:
    kind: str
    key: str = ""
    label: str = ""
    description: str = ""
    order: int = 0

    def _base_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "order": self.order,
        }

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass
class PrimitiveField(FieldNode):
    kind: str = "primitive"
    type: Literal["str", "int", "float", "bool", "enum", "literal"] = "str"
    default: Any = None
    required: bool = True
    secret: bool = False
    choices: list[dict[str, str]] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = self._base_dict()
        d.update(
            {
                "type": self.type,
                "default": self.default,
                "required": self.required,
                "secret": self.secret,
            }
        )
        if self.choices is not None:
            d["choices"] = self.choices
        return d


@dataclass
class ObjectField(FieldNode):
    kind: str = "object"
    children: list[FieldNode] = field(default_factory=list)
    default: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = self._base_dict()
        d["children"] = [child.to_dict() for child in self.children]
        if self.default is not None:
            d["default"] = self.default
        return d


@dataclass
class ArrayField(FieldNode):
    kind: str = "array"
    item_schema: FieldNode | None = None
    default: list[Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = self._base_dict()
        if self.item_schema is not None:
            d["item_schema"] = self.item_schema.to_dict()
        if self.default is not None:
            d["default"] = self.default
        return d


@dataclass
class MapField(FieldNode):
    kind: str = "map"
    key_type: str = "str"
    value_schema: FieldNode | None = None

    def to_dict(self) -> dict[str, Any]:
        d = self._base_dict()
        d["key_type"] = self.key_type
        if self.value_schema is not None:
            d["value_schema"] = self.value_schema.to_dict()
        return d


@dataclass
class AnyField(FieldNode):
    kind: str = "any"
    default: Any = None

    def to_dict(self) -> dict[str, Any]:
        d = self._base_dict()
        d["default"] = self.default
        return d


@dataclass
class ConfigContract:
    namespace: str | None
    is_scoped: bool
    owner_kind: Literal["plugin", "adapter", "nonebot", "apeiria"]
    owner_id: str
    source: Literal["pydantic", "extra_only", "none"]
    fields: list[FieldNode]
    json_schema: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "is_scoped": self.is_scoped,
            "owner_kind": self.owner_kind,
            "owner_id": self.owner_id,
            "source": self.source,
            "fields": [f.to_dict() for f in self.fields],
            "json_schema": self.json_schema,
        }

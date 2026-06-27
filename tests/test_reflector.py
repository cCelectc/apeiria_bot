from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from apeiria.config.reflector import reflect_model
from apeiria.config.schema import ArrayField, ObjectField, PrimitiveField


class Color(Enum):
    RED = "red"
    BLUE = "blue"


class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432


class WeatherConfig(BaseModel):
    api_key: str = ""
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)


class FlatConfig(BaseModel):
    count: int = 3
    cooldown: float = 5.0
    enabled: bool = True
    mode: Literal["ws", "ws-reverse"] = "ws"
    color: Color = Color.BLUE
    labels: list[str] = Field(default_factory=list)
    extra: str | None = None


class NestedConfig(BaseModel):
    weather: WeatherConfig
    api_key: str = ""


def test_reflect_flat_primitive_fields() -> None:
    fields = reflect_model(FlatConfig)
    assert len(fields) == 7

    count_f = next(f for f in fields if f.key == "count")
    assert isinstance(count_f, PrimitiveField)
    assert count_f.type == "int"
    assert count_f.default == 3
    assert count_f.required is False  # has default

    cooldown_f = next(f for f in fields if f.key == "cooldown")
    assert isinstance(cooldown_f, PrimitiveField)
    assert cooldown_f.type == "float"

    enabled_f = next(f for f in fields if f.key == "enabled")
    assert isinstance(enabled_f, PrimitiveField)
    assert enabled_f.type == "bool"
    assert enabled_f.default is True

    labels_f = next(f for f in fields if f.key == "labels")
    assert isinstance(labels_f, ArrayField)
    assert labels_f.item_schema is not None
    assert labels_f.item_schema.kind == "primitive"
    assert labels_f.item_schema.type == "str"

    extra_f = next(f for f in fields if f.key == "extra")
    assert isinstance(extra_f, PrimitiveField)
    assert extra_f.required is False


def test_reflect_literal_field() -> None:
    fields = reflect_model(FlatConfig)
    mode_f = next(f for f in fields if f.key == "mode")
    assert isinstance(mode_f, PrimitiveField)
    assert mode_f.type == "literal"
    assert mode_f.choices is not None
    assert len(mode_f.choices) == 2


def test_reflect_enum_field() -> None:
    fields = reflect_model(FlatConfig)
    color_f = next(f for f in fields if f.key == "color")
    assert isinstance(color_f, PrimitiveField)
    assert color_f.type == "enum"
    assert color_f.choices is not None
    assert len(color_f.choices) == 2


def test_reflect_nested_object_field() -> None:
    fields = reflect_model(NestedConfig)
    weather_f = next(f for f in fields if f.key == "weather")
    assert isinstance(weather_f, ObjectField)
    assert len(weather_f.children) == 2

    child_keys = {c.key for c in weather_f.children}
    assert child_keys == {"api_key", "db"}

    db_f = next(c for c in weather_f.children if c.key == "db")
    assert isinstance(db_f, ObjectField)
    assert len(db_f.children) == 2
    db_child_keys = {c.key for c in db_f.children}
    assert db_child_keys == {"host", "port"}

    host_f = next(c for c in db_f.children if c.key == "host")
    assert isinstance(host_f, PrimitiveField)
    assert host_f.type == "str"
    assert host_f.default == "localhost"


def test_reflect_field_description_and_title() -> None:
    class WithMeta(BaseModel):
        name: str = Field(default="", title="名称", description="用户名称")

    fields = reflect_model(WithMeta)
    f = fields[0]
    assert f.label == "名称"
    assert f.description == "用户名称"


def test_reflect_flat_model_is_all_primitive() -> None:
    fields = reflect_model(FlatConfig)
    for f in fields:
        if f.key == "labels":
            assert isinstance(f, ArrayField)
        else:
            assert isinstance(f, PrimitiveField)


def test_reflect_nested_model_has_object() -> None:
    fields = reflect_model(NestedConfig)
    kinds = {f.kind for f in fields}
    assert "object" in kinds

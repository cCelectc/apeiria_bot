from __future__ import annotations

from apeiria.config.schema import (
    AnyField,
    ArrayField,
    ConfigContract,
    ObjectField,
    PrimitiveField,
)


def test_primitive_field_serialization() -> None:
    f = PrimitiveField(
        key="api_key",
        label="API Key",
        description="The key",
        type="str",
        default="",
        required=True,
        secret=True,
        choices=[{"value": "a", "label": "A"}],
        order=1,
    )
    d = f.to_dict()
    assert d["kind"] == "primitive"
    assert d["key"] == "api_key"
    assert d["type"] == "str"
    assert d["secret"] is True
    assert d["choices"] == [{"value": "a", "label": "A"}]


def test_object_field_recursive_serialization() -> None:
    child = PrimitiveField(
        key="host",
        label="Host",
        type="str",
        default="localhost",
        required=True,
    )
    parent = ObjectField(
        key="db",
        label="Database",
        children=[child],
        default={"host": "localhost"},
    )
    d = parent.to_dict()
    assert d["kind"] == "object"
    assert len(d["children"]) == 1
    assert d["children"][0]["key"] == "host"


def test_array_field_serialization() -> None:
    item = ObjectField(
        key="",
        label="Mirror",
        children=[
            PrimitiveField(key="url", label="URL", type="str", required=True),
            PrimitiveField(
                key="priority", label="Priority", type="int", default=0, required=False
            ),
        ],
    )
    arr = ArrayField(
        key="mirrors",
        label="Mirrors",
        item_schema=item,
        default=[],
    )
    d = arr.to_dict()
    assert d["kind"] == "array"
    assert d["item_schema"]["kind"] == "object"
    assert len(d["item_schema"]["children"]) == 2


def test_config_contract_serialization() -> None:
    c = ConfigContract(
        namespace="weather",
        is_scoped=True,
        owner_kind="plugin",
        owner_id="weather_plugin",
        source="pydantic",
        fields=[
            PrimitiveField(
                key="api_key", label="Key", type="str", required=True, order=1
            ),
        ],
        json_schema={"type": "object", "properties": {}},
    )
    d = c.to_dict()
    assert d["namespace"] == "weather"
    assert d["is_scoped"] is True
    assert d["owner_kind"] == "plugin"
    assert d["source"] == "pydantic"
    assert len(d["fields"]) == 1
    assert "json_schema" in d


def test_default_order_is_zero() -> None:
    f = PrimitiveField(key="x", label="X", type="str", required=True)
    assert f.order == 0


def test_any_field_serialization() -> None:
    f = AnyField(key="custom", label="Custom", description="Free form", default=None)
    d = f.to_dict()
    assert d["kind"] == "any"

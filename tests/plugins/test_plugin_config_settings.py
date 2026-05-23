from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import BaseModel

from apeiria.plugins.metadata.api import PluginExtraData, RegisterConfig
from apeiria.plugins.metadata.registry import configs_from_model
from apeiria.plugins.metadata.resolver import (
    _merge_declared_configs,
    resolve_config_namespace_contract,
)
from apeiria.plugins.settings_capabilities import (
    get_field_capability,
    normalize_value_for_response,
)

CUSTOM_FIELD_ORDER = 10


class OwnerHandle(BaseModel):
    scope: str
    target_id: str


class RuntimeTupleConfig(BaseModel):
    owner_targets: tuple[OwnerHandle, ...] = ()


def test_metadata_shape_override_replaces_model_tuple_field() -> None:
    base = configs_from_model(RuntimeTupleConfig)
    enhancement = RegisterConfig(
        key="owner_targets",
        default=[],
        help="Owner private message targets.",
        type=list,
        item_type=str,
        label="Owner targets",
        order=CUSTOM_FIELD_ORDER,
    )

    merged = _merge_declared_configs(base, [enhancement])
    field = merged[0]

    assert field.type is list
    assert field.default == []
    assert field.item_type is str
    assert field.item_schema is None
    assert field.help == "Owner private message targets."
    assert field.label == "Owner targets"
    assert field.order == CUSTOM_FIELD_ORDER


def test_sparse_metadata_preserves_model_shape_for_presentation_only() -> None:
    base = configs_from_model(RuntimeTupleConfig)
    extra = PluginExtraData.from_extra(
        {
            "_apeiria": True,
            "config": {
                "fields": [
                    {
                        "key": "owner_targets",
                        "help": "Shown in settings.",
                        "label": "Owner targets",
                        "order": CUSTOM_FIELD_ORDER,
                    }
                ]
            },
        }
    )
    assert extra is not None

    merged = _merge_declared_configs(base, extra.configs)
    field = merged[0]

    assert field.type is list
    assert field.default == ()
    assert field.item_schema is not None
    assert field.item_schema.type is OwnerHandle
    assert field.help == "Shown in settings."
    assert field.label == "Owner targets"
    assert field.order == CUSTOM_FIELD_ORDER


def test_runtime_tuple_annotation_builds_sequence_schema() -> None:
    field = configs_from_model(RuntimeTupleConfig)[0]

    assert field.type is list
    assert field.default == ()
    assert field.item_schema is not None
    assert field.item_schema.type is OwnerHandle
    assert [item.key for item in field.item_schema.fields] == ["scope", "target_id"]


def test_settings_response_normalizes_collections_and_models() -> None:
    field = configs_from_model(RuntimeTupleConfig)[0]
    value = (OwnerHandle(scope="qq", target_id="123456"),)

    assert normalize_value_for_response(field, field.default) == []
    assert normalize_value_for_response(field, value) == [
        {"scope": "qq", "target_id": "123456"}
    ]

    string_list = RegisterConfig(
        key="items",
        default=("a", "b"),
        type=list,
        item_type=str,
    )
    assert normalize_value_for_response(string_list, string_list.default) == ["a", "b"]


def test_string_list_mutation_accepts_strings_and_rejects_non_strings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import nonebot

    monkeypatch.setattr(nonebot, "get_plugin_config", lambda model: model())
    settings_support = importlib.import_module("apeiria.plugins.settings_support")
    field = RegisterConfig(
        key="owner_targets",
        default=[],
        type=list,
        item_type=str,
    )

    assert settings_support.validate_and_coerce_updates(
        {"owner_targets": ["qq:123456"]},
        [],
        [field],
    ) == {"owner_targets": ["qq:123456"]}
    assert settings_support.validate_and_coerce_updates(
        {"owner_targets": []},
        [],
        [field],
    ) == {"owner_targets": None}

    with pytest.raises(HTTPException):
        settings_support.validate_and_coerce_updates(
            {"owner_targets": ["qq:123456", 123456]},
            [],
            [field],
        )


def test_contact_approval_owner_targets_are_exposed_as_string_chips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apeiria.plugins.metadata import resolver

    module = importlib.import_module("apeiria.builtin_plugins.contact_approval")
    monkeypatch.setattr(
        resolver.nonebot,
        "get_loaded_plugins",
        lambda: [
            SimpleNamespace(
                module_name="apeiria.builtin_plugins.contact_approval",
                metadata=module.__plugin_meta__,
            )
        ],
    )

    contract = resolve_config_namespace_contract(
        "apeiria.builtin_plugins.contact_approval"
    )
    fields = {field.key: field for field in contract.configs}
    owner_targets = fields["owner_targets"]

    assert owner_targets.type is list
    assert owner_targets.item_type is str
    assert owner_targets.default == []
    assert owner_targets.item_schema is None
    assert get_field_capability(owner_targets).editor == "chips"


def test_contact_approval_saved_owner_targets_remain_runtime_compatible() -> None:
    from apeiria.builtin_plugins.contact_approval.config import (
        OwnerTarget,
        normalize_contact_approval_config,
    )

    normalized = normalize_contact_approval_config(
        {"owner_targets": ["qq:123456", "bad", "qq:0"]}
    )

    assert normalized["owner_targets"] == (OwnerTarget(scope="qq", target_id="123456"),)

from __future__ import annotations

import pytest

from apeiria.config.schema import ConfigContract, PrimitiveField
from apeiria.plugin.metadata.resolver import (
    merge_extra_hints,
    resolve_config_namespace_contract,
)


def test_merge_extra_hints_adds_label() -> None:
    fields = [
        PrimitiveField(key="api_key", label="api_key", type="str", required=True),
    ]
    extra_hints = [
        {"key": "api_key", "label": "API密钥", "secret": True, "order": 5},
    ]
    merge_extra_hints(fields, extra_hints)
    f = fields[0]
    assert f.label == "API密钥"
    assert f.secret is True
    assert f.order == 5


def test_merge_extra_hints_preserves_pydantic_when_no_extra() -> None:
    fields = [
        PrimitiveField(
            key="host",
            label="HostName",
            description="The host",
            type="str",
            required=True,
        ),
    ]
    merge_extra_hints(fields, [])
    f = fields[0]
    assert f.label == "HostName"
    assert f.description == "The host"


def test_merge_extra_hints_extra_missing_key_ignored() -> None:
    fields = [
        PrimitiveField(key="host", label="host", type="str", required=True),
    ]
    merge_extra_hints(fields, [{"key": "nonexistent", "label": "N/A"}])
    f = fields[0]
    assert f.label == "host"


@pytest.mark.asyncio
async def test_resolve_contract_flat_model() -> None:
    contract = resolve_config_namespace_contract("apeiria.builtin_plugins.repeater")
    assert isinstance(contract, ConfigContract)
    assert contract.owner_kind == "plugin"
    assert contract.is_scoped is False
    assert contract.namespace is None


@pytest.mark.asyncio
async def test_resolve_contract_unknown_plugin() -> None:
    contract = resolve_config_namespace_contract("nonexistent.plugin.name")
    assert isinstance(contract, ConfigContract)
    assert contract.source == "none"
    assert contract.fields == []


@pytest.mark.asyncio
async def test_resolve_contract_pypi_plugin_by_manifest_name(monkeypatch) -> None:
    from typing import ClassVar

    import nonebot
    from pydantic import BaseModel

    from apeiria.plugin import scanner
    from apeiria.plugin.scanner import PluginManifest

    class _FakeConfig(BaseModel):
        api_key: str = ""

    class _FakeMeta:
        config = _FakeConfig
        extra: ClassVar[dict] = {}

    class _FakePlugin:
        name = "nonebot_plugin_status"
        module_name = "nonebot_plugin_status"
        metadata = _FakeMeta()

    monkeypatch.setattr(nonebot, "get_loaded_plugins", lambda: {_FakePlugin()})
    monkeypatch.setattr(
        scanner,
        "scan_plugins",
        lambda: [
            PluginManifest(
                name="服务器状态查看",
                path_or_module="nonebot-plugin-status>=0.9.0",
                enabled=True,
                source="pypi",
            )
        ],
    )

    contract = resolve_config_namespace_contract("服务器状态查看")
    assert contract.source == "pydantic"
    assert contract.owner_kind == "plugin"
    assert any(f.key == "api_key" for f in contract.fields)

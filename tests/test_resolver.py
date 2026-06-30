from __future__ import annotations

import pytest

from apeiria.config.contract import resolve_config_namespace_contract
from apeiria.config.schema import ConfigContract


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

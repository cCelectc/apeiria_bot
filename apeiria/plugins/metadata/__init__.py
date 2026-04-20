"""Plugin metadata declaration, registry, and scanning services."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.plugins.metadata.contracts import ConfigNamespaceContract
    from apeiria.plugins.metadata.registry import (
        PluginConfigConflictError,
        RegisterPluginConfigOptions,
        configs_from_model,
        get_registered_plugin_config,
        iter_registered_plugin_configs,
        register_plugin_config,
    )
    from apeiria.plugins.metadata.resolver import (
        PluginScanCandidate,
        collect_plugin_config_candidates,
        ensure_config_namespace_contract,
        resolve_config_namespace_contract,
    )

__all__ = [
    "ConfigNamespaceContract",
    "PluginConfigConflictError",
    "PluginScanCandidate",
    "RegisterPluginConfigOptions",
    "collect_plugin_config_candidates",
    "configs_from_model",
    "ensure_config_namespace_contract",
    "get_registered_plugin_config",
    "iter_registered_plugin_configs",
    "register_plugin_config",
    "resolve_config_namespace_contract",
]


def __getattr__(name: str) -> object:
    if name in {
        "ConfigNamespaceContract",
        "PluginConfigConflictError",
        "RegisterPluginConfigOptions",
        "configs_from_model",
        "get_registered_plugin_config",
        "iter_registered_plugin_configs",
        "register_plugin_config",
    }:
        from apeiria.plugins.metadata import contracts, registry

        if name == "ConfigNamespaceContract":
            return getattr(contracts, name)
        return getattr(registry, name)

    if name in {
        "PluginScanCandidate",
        "collect_plugin_config_candidates",
        "ensure_config_namespace_contract",
        "resolve_config_namespace_contract",
    }:
        from apeiria.plugins.metadata import resolver

        return getattr(resolver, name)

    raise AttributeError(name)

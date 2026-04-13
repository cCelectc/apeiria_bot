"""Plugin metadata declaration, registry, and scanning services."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.infra.plugin_metadata.registry import (
        PluginConfigConflictError,
        RegisterPluginConfigOptions,
        configs_from_model,
        get_registered_plugin_config,
        iter_registered_plugin_configs,
        register_plugin_config,
    )
    from apeiria.infra.plugin_metadata.resolver import (
        PluginScanCandidate,
        ResolvedPluginConfig,
        collect_plugin_config_candidates,
        ensure_plugin_config_registration,
        resolve_plugin_declared_config,
    )

__all__ = [
    "PluginConfigConflictError",
    "PluginScanCandidate",
    "RegisterPluginConfigOptions",
    "ResolvedPluginConfig",
    "collect_plugin_config_candidates",
    "configs_from_model",
    "ensure_plugin_config_registration",
    "get_registered_plugin_config",
    "iter_registered_plugin_configs",
    "register_plugin_config",
    "resolve_plugin_declared_config",
]


def __getattr__(name: str) -> object:
    if name in {
        "PluginConfigConflictError",
        "RegisterPluginConfigOptions",
        "configs_from_model",
        "get_registered_plugin_config",
        "iter_registered_plugin_configs",
        "register_plugin_config",
    }:
        from apeiria.infra.plugin_metadata import registry

        return getattr(registry, name)

    if name in {
        "PluginScanCandidate",
        "ResolvedPluginConfig",
        "collect_plugin_config_candidates",
        "ensure_plugin_config_registration",
        "resolve_plugin_declared_config",
    }:
        from apeiria.infra.plugin_metadata import resolver

        return getattr(resolver, name)

    raise AttributeError(name)

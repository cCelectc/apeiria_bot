"""Plugin application-facing services.

Lazy exports keep the CLI usable before ``nonebot.init(...)`` has run, since
some submodules (e.g. repository) import ``nonebot_plugin_orm`` at top level.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apeiria.plugins.catalog import (
        PluginGovernanceService,
        plugin_governance_service,
    )
    from apeiria.plugins.models import (
        HandlerDescriptor,
        PluginCatalogEntry,
        PluginDescriptor,
        PluginGovernanceState,
        PluginPackageBinding,
        PluginRuntimeState,
        PluginUninstallResult,
    )
    from apeiria.plugins.policy import (
        PluginPolicyService,
        plugin_policy_service,
    )
    from apeiria.plugins.readme import PluginReadme
    from apeiria.plugins.registry import (
        AdapterConfigState,
        DriverConfigState,
        PluginConfigState,
    )
    from apeiria.plugins.settings import (
        ConfigFieldView,
        ConfigMutation,
        ConfigMutationKind,
        ConfigMutationService,
        ConfigQueryService,
        ConfigSchemaService,
        ConfigTextView,
        ConfigValidationReport,
        ConfigView,
        PluginConfigConflictError,
        PluginSettingsNotConfigurableError,
        config_mutation_service,
        config_query_service,
        config_schema_service,
    )
    from apeiria.plugins.settings_cleanup import OrphanPluginConfigItem
    from apeiria.plugins.settings_support import UnknownPluginSettingFieldError

__all__ = [
    "AdapterConfigState",
    "ConfigFieldView",
    "ConfigMutation",
    "ConfigMutationKind",
    "ConfigMutationService",
    "ConfigQueryService",
    "ConfigSchemaService",
    "ConfigTextView",
    "ConfigValidationReport",
    "ConfigView",
    "DriverConfigState",
    "HandlerDescriptor",
    "OrphanPluginConfigItem",
    "PluginCatalogEntry",
    "PluginConfigConflictError",
    "PluginConfigState",
    "PluginDescriptor",
    "PluginGovernanceService",
    "PluginGovernanceState",
    "PluginPackageBinding",
    "PluginPolicyService",
    "PluginReadme",
    "PluginRuntimeState",
    "PluginSettingsNotConfigurableError",
    "PluginUninstallResult",
    "UnknownPluginSettingFieldError",
    "config_mutation_service",
    "config_query_service",
    "config_schema_service",
    "plugin_governance_service",
    "plugin_policy_service",
]

_LAZY_MODULES = {
    "AdapterConfigState": "apeiria.plugins.registry",
    "DriverConfigState": "apeiria.plugins.registry",
    "PluginConfigState": "apeiria.plugins.registry",
    "ConfigFieldView": "apeiria.plugins.settings",
    "ConfigMutation": "apeiria.plugins.settings",
    "ConfigMutationKind": "apeiria.plugins.settings",
    "ConfigMutationService": "apeiria.plugins.settings",
    "ConfigQueryService": "apeiria.plugins.settings",
    "ConfigSchemaService": "apeiria.plugins.settings",
    "ConfigTextView": "apeiria.plugins.settings",
    "ConfigValidationReport": "apeiria.plugins.settings",
    "ConfigView": "apeiria.plugins.settings",
    "PluginConfigConflictError": "apeiria.plugins.settings",
    "PluginSettingsNotConfigurableError": "apeiria.plugins.settings",
    "config_mutation_service": "apeiria.plugins.settings",
    "config_query_service": "apeiria.plugins.settings",
    "config_schema_service": "apeiria.plugins.settings",
    "PluginCatalogEntry": "apeiria.plugins.models",
    "PluginDescriptor": "apeiria.plugins.models",
    "HandlerDescriptor": "apeiria.plugins.models",
    "PluginGovernanceState": "apeiria.plugins.models",
    "PluginPackageBinding": "apeiria.plugins.models",
    "PluginRuntimeState": "apeiria.plugins.models",
    "PluginUninstallResult": "apeiria.plugins.models",
    "OrphanPluginConfigItem": "apeiria.plugins.settings_cleanup",
    "PluginReadme": "apeiria.plugins.readme",
    "PluginPolicyService": "apeiria.plugins.policy",
    "plugin_policy_service": "apeiria.plugins.policy",
    "PluginGovernanceService": "apeiria.plugins.catalog",
    "plugin_governance_service": "apeiria.plugins.catalog",
    "UnknownPluginSettingFieldError": "apeiria.plugins.settings_support",
}


def __getattr__(name: str) -> Any:
    module_path = _LAZY_MODULES.get(name)
    if module_path is not None:
        module = import_module(module_path)
        return getattr(module, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)

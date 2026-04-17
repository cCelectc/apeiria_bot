"""Plugin application-facing services.

Use lazy exports so importing one submodule does not eagerly pull the whole
plugin management stack into memory during unrelated startup paths.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apeiria.app.plugins.config_cleanup_service import OrphanPluginConfigItem
    from apeiria.app.plugins.config_service import (
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
    from apeiria.app.plugins.models import (
        HandlerDescriptor,
        PluginCatalogEntry,
        PluginDescriptor,
        PluginGovernanceState,
        PluginPackageBinding,
        PluginRuntimeState,
        PluginUninstallResult,
    )
    from apeiria.app.plugins.policy_service import (
        PluginPolicyService,
        plugin_policy_service,
    )
    from apeiria.app.plugins.readme_service import PluginReadme
    from apeiria.app.plugins.registration_service import (
        AdapterConfigState,
        DriverConfigState,
        PluginConfigState,
    )
    from apeiria.app.plugins.service import (
        PluginGovernanceService,
        plugin_governance_service,
    )
    from apeiria.app.plugins.settings_support import UnknownPluginSettingFieldError

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
    "AdapterConfigState": "apeiria.app.plugins.config_service",
    "ConfigFieldView": "apeiria.app.plugins.config_service",
    "ConfigMutation": "apeiria.app.plugins.config_service",
    "ConfigMutationKind": "apeiria.app.plugins.config_service",
    "ConfigMutationService": "apeiria.app.plugins.config_service",
    "ConfigQueryService": "apeiria.app.plugins.config_service",
    "ConfigSchemaService": "apeiria.app.plugins.config_service",
    "ConfigTextView": "apeiria.app.plugins.config_service",
    "ConfigValidationReport": "apeiria.app.plugins.config_service",
    "ConfigView": "apeiria.app.plugins.config_service",
    "DriverConfigState": "apeiria.app.plugins.config_service",
    "PluginConfigConflictError": "apeiria.app.plugins.config_service",
    "PluginConfigState": "apeiria.app.plugins.config_service",
    "PluginSettingsNotConfigurableError": "apeiria.app.plugins.config_service",
    "config_mutation_service": "apeiria.app.plugins.config_service",
    "config_query_service": "apeiria.app.plugins.config_service",
    "config_schema_service": "apeiria.app.plugins.config_service",
    "PluginCatalogEntry": "apeiria.app.plugins.models",
    "PluginDescriptor": "apeiria.app.plugins.models",
    "HandlerDescriptor": "apeiria.app.plugins.models",
    "PluginGovernanceState": "apeiria.app.plugins.models",
    "PluginPackageBinding": "apeiria.app.plugins.models",
    "PluginRuntimeState": "apeiria.app.plugins.models",
    "PluginUninstallResult": "apeiria.app.plugins.models",
    "OrphanPluginConfigItem": "apeiria.app.plugins.config_cleanup_service",
    "PluginReadme": "apeiria.app.plugins.readme_service",
    "PluginPolicyService": "apeiria.app.plugins.policy_service",
    "plugin_policy_service": "apeiria.app.plugins.policy_service",
    "PluginGovernanceService": "apeiria.app.plugins.service",
    "plugin_governance_service": "apeiria.app.plugins.service",
    "UnknownPluginSettingFieldError": "apeiria.app.plugins.settings_support",
}


def __getattr__(name: str) -> Any:
    module_path = _LAZY_MODULES.get(name)
    if module_path is not None:
        module = import_module(module_path)
        return getattr(module, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)

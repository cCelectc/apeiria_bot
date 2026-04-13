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
        PluginConfigConflictError,
        PluginConfigViewService,
        PluginRawSettingsState,
        PluginRawValidationState,
        PluginSettingsNotConfigurableError,
        PluginSettingsState,
        plugin_config_view_service,
    )
    from apeiria.app.plugins.models import PluginUninstallResult
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
        PluginCatalogItem,
        PluginCatalogService,
        plugin_catalog_service,
    )
    from apeiria.app.plugins.settings_support import UnknownPluginSettingFieldError

__all__ = [
    "AdapterConfigState",
    "DriverConfigState",
    "OrphanPluginConfigItem",
    "PluginCatalogItem",
    "PluginCatalogService",
    "PluginConfigConflictError",
    "PluginConfigState",
    "PluginConfigViewService",
    "PluginPolicyService",
    "PluginRawSettingsState",
    "PluginRawValidationState",
    "PluginReadme",
    "PluginSettingsNotConfigurableError",
    "PluginSettingsState",
    "PluginUninstallResult",
    "UnknownPluginSettingFieldError",
    "plugin_catalog_service",
    "plugin_config_view_service",
    "plugin_policy_service",
]

_LAZY_MODULES = {
    "AdapterConfigState": "apeiria.app.plugins.config_service",
    "DriverConfigState": "apeiria.app.plugins.config_service",
    "PluginConfigConflictError": "apeiria.app.plugins.config_service",
    "PluginConfigState": "apeiria.app.plugins.config_service",
    "PluginConfigViewService": "apeiria.app.plugins.config_service",
    "PluginRawSettingsState": "apeiria.app.plugins.config_service",
    "PluginRawValidationState": "apeiria.app.plugins.config_service",
    "PluginSettingsNotConfigurableError": "apeiria.app.plugins.config_service",
    "PluginSettingsState": "apeiria.app.plugins.config_service",
    "plugin_config_view_service": "apeiria.app.plugins.config_service",
    "PluginUninstallResult": "apeiria.app.plugins.models",
    "OrphanPluginConfigItem": "apeiria.app.plugins.config_cleanup_service",
    "PluginReadme": "apeiria.app.plugins.readme_service",
    "PluginPolicyService": "apeiria.app.plugins.policy_service",
    "plugin_policy_service": "apeiria.app.plugins.policy_service",
    "PluginCatalogItem": "apeiria.app.plugins.service",
    "PluginCatalogService": "apeiria.app.plugins.service",
    "plugin_catalog_service": "apeiria.app.plugins.service",
    "UnknownPluginSettingFieldError": "apeiria.app.plugins.settings_support",
}


def __getattr__(name: str) -> Any:
    module_path = _LAZY_MODULES.get(name)
    if module_path is not None:
        module = import_module(module_path)
        return getattr(module, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)

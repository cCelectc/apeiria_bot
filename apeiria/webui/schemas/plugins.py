"""Unified plugin schemas (catalog, config, management, store, workbench)."""

from apeiria.webui.schemas.plugin_catalog import (  # noqa: F401
    OrphanPluginConfigResponse,
    PluginItem,
    PluginReadmeResponse,
    PluginUpdateCheckItem,
    PluginUpdateCheckRequest,
    PluginWorkspaceResponse,
)
from apeiria.webui.schemas.plugin_config import (  # noqa: F401
    AdapterConfigRequest,
    AdapterConfigResponse,
    DriverConfigRequest,
    DriverConfigResponse,
    PluginConfigRequest,
    PluginConfigResponse,
    PluginRawSettingsResponse,
    PluginSettingsRawUpdateRequest,
    PluginSettingsRawValidationResponse,
    PluginSettingsResponse,
    PluginSettingsUpdateRequest,
)
from apeiria.webui.schemas.plugin_management import (  # noqa: F401
    PluginInstallConfirmRequest,
    PluginInstallResolveRequest,
    PluginInstallResolveResponse,
    PluginManualInstallRequest,
    PluginPackageUpdateRequest,
    PluginPolicyUpdateRequest,
    PluginPolicyUpdateResponse,
    PluginTogglePreviewResponse,
    PluginToggleResponse,
    PluginUninstallRequest,
)
from apeiria.webui.schemas.plugin_store import (  # noqa: F401
    PluginStoreCategoryItem,
    PluginStoreInstallRequest,
    PluginStoreItem,
    PluginStoreItemsResponse,
    PluginStoreRevertInstallRequest,
    PluginStoreSourceItem,
    PluginStoreTaskItem,
)
from apeiria.webui.schemas.plugin_workbench import PluginWorkbenchResponse  # noqa: F401

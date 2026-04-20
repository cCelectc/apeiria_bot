"""Pydantic request/response schemas for Web UI API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Credentials used by the Web UI login endpoint."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class WebUIPrincipalResponse(BaseModel):
    """Authenticated Web UI user information."""

    user_id: str
    username: str
    role: str
    capabilities: list[str] = []


class LoginResponse(BaseModel):
    """Successful login response."""

    token: str
    principal: WebUIPrincipalResponse


class RegisterRequest(BaseModel):
    """Payload used to create a new Web UI account with a registration code."""

    registration_code: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class RegisterResponse(BaseModel):
    """Registration result returned by the Web UI API."""

    status: str = "ok"
    detail: str | None = None


class WebUIAccountItem(BaseModel):
    """Stored Web UI account information returned to account managers."""

    user_id: str
    username: str
    role: str
    is_disabled: bool = False
    last_login_at: str | None = None
    password_changed_at: str | None = None


class PasswordChangeRequest(BaseModel):
    """Request payload used to rotate a password."""

    current_password: str | None = Field(default=None, min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class RoleUpdateRequest(BaseModel):
    """Request payload used to change an account role."""

    role: str = Field(min_length=1, max_length=32)


class SessionRefreshResponse(BaseModel):
    """Response used when the current session must rotate in place."""

    status: str = "ok"
    detail: str | None = None
    token: str
    principal: WebUIPrincipalResponse


class SecurityAuditEventItem(BaseModel):
    """Security audit event returned to account managers."""

    event_type: str
    occurred_at: str
    actor_username: str | None = None
    target_username: str | None = None
    detail: str | None = None


class StatusResponse(BaseModel):
    status: str
    uptime: float
    plugins_count: int
    disabled_plugins_count: int
    groups_count: int
    disabled_groups_count: int
    access_rules_count: int
    adapters: list[str]


class DashboardEventItem(BaseModel):
    """Recent dashboard event item."""

    timestamp: str
    level: str
    source: str
    message: str


class DashboardEventsResponse(BaseModel):
    """Recent dashboard events response."""

    items: list[DashboardEventItem]


class LogItem(BaseModel):
    """Structured log item returned by the Web UI log APIs."""

    timestamp: str
    level: str
    source: str
    message: str
    raw: str
    extra: dict[str, object] = {}


class LogHistoryQuery(BaseModel):
    """History log query parameters."""

    level: str = ""
    source: str = ""
    search: str = ""
    start: str = ""
    end: str = ""
    include_access: bool = True


class LogHistoryResponse(BaseModel):
    """Paginated persisted log history response."""

    items: list[LogItem]
    total: int = 0
    before: int
    next_before: int | None = None
    has_more: bool = False


class LogSourcesResponse(BaseModel):
    """Available log sources for history filtering."""

    items: list[str]


class WebUIBuildStatusResponse(BaseModel):
    """Current Web UI frontend build status."""

    is_built: bool
    is_stale: bool
    can_build: bool
    build_tool: str | None = None
    detail: str | None = None


class WebUIBuildRunResponse(WebUIBuildStatusResponse):
    """Web UI frontend rebuild response with build logs."""

    logs: str = ""


class PluginItem(BaseModel):
    module_name: str
    kind: str = "plugin"
    access_mode: str = "default_allow"
    name: str | None
    description: str | None
    homepage: str | None = None
    source: str
    is_global_enabled: bool
    is_protected: bool = False
    protected_reason: str | None = None
    plugin_type: str = "normal"
    admin_level: int = 0
    author: str | None = None
    version: str | None = None
    is_loaded: bool = True
    is_explicit: bool = False
    is_dependency: bool = False
    is_pending_uninstall: bool = False
    can_edit_config: bool = True
    can_view_readme: bool = False
    can_enable_disable: bool = False
    can_uninstall: bool = False
    can_package_update: bool = False
    child_plugins: list[str] = []
    required_plugins: list[str] = []
    dependent_plugins: list[str] = []
    installed_package: str | None = None
    installed_module_names: list[str] = []


class PluginUpdateCheckRequest(BaseModel):
    """Plugin update check request payload."""

    force_refresh: bool = False


class PluginUpdateCheckItem(BaseModel):
    """One plugin update check result returned to the Web UI."""

    module_name: str
    package_name: str
    current_version: str | None = None
    latest_version: str | None = None
    has_update: bool = False
    checked: bool = False
    error: str | None = None


class PluginTogglePreviewResponse(BaseModel):
    module_name: str
    enabled: bool
    allowed: bool = True
    summary: str = ""
    blocked_reason: str | None = None
    requires_enable: list[str] = []
    requires_disable: list[str] = []
    protected_dependents: list[str] = []
    missing_dependencies: list[str] = []


class PluginToggleResponse(BaseModel):
    module_name: str
    enabled: bool
    affected_modules: list[str] = []


class PluginReadmeResponse(BaseModel):
    module_name: str
    filename: str
    content: str


class AccessRuleItem(BaseModel):
    subject_type: str
    subject_id: str
    plugin_module: str
    effect: str
    note: str | None = None


class AccessRuleCreateRequest(BaseModel):
    subject_type: str = Field(min_length=1, max_length=16)
    subject_id: str = Field(min_length=1, max_length=64)
    plugin_module: str = Field(min_length=1, max_length=256)
    effect: str = Field(min_length=1, max_length=16)
    note: str | None = Field(default=None, max_length=512)


class AccessRuleDeleteRequest(BaseModel):
    subject_type: str = Field(min_length=1, max_length=16)
    subject_id: str = Field(min_length=1, max_length=64)
    plugin_module: str = Field(min_length=1, max_length=256)


class PluginAccessModeUpdateRequest(BaseModel):
    access_mode: str = Field(min_length=1, max_length=16)


class PluginStoreSourceItem(BaseModel):
    """Plugin store source returned to the Web UI."""

    source_id: str
    name: str
    kind: str
    enabled: bool = True
    is_builtin: bool = False
    is_official: bool = False
    base_url: str | None = None
    last_synced_at: str | None = None
    last_error: str | None = None


class PluginStoreItem(BaseModel):
    """Plugin store item returned to the Web UI."""

    source_id: str
    source_name: str
    plugin_id: str
    name: str
    module_name: str
    package_name: str
    description: str | None = None
    project_link: str | None = None
    homepage: str | None = None
    author: str | None = None
    author_link: str | None = None
    version: str | None = None
    tags: list[str] = []
    is_official: bool = False
    publish_time: str | None = None
    extra: dict[str, object] = {}
    is_installed: bool = False
    is_registered: bool = False
    installed_package: str | None = None
    installed_module_names: list[str] = []
    can_update: bool = False


class PluginStoreCategoryItem(BaseModel):
    """Plugin store category aggregate returned to the Web UI."""

    value: str
    count: int


class PluginStoreItemsResponse(BaseModel):
    """Paginated plugin store items response."""

    items: list[PluginStoreItem]
    categories: list[PluginStoreCategoryItem] = []
    total: int
    page: int
    per_page: int


class PluginStoreInstallRequest(BaseModel):
    """Plugin store install request payload."""

    source_id: str = Field(min_length=1, max_length=128)
    plugin_id: str = Field(min_length=1, max_length=256)
    package_name: str = Field(min_length=1, max_length=256)
    module_name: str = Field(min_length=1, max_length=256)


class PluginStoreRevertInstallRequest(BaseModel):
    """Revert one pending plugin-store install."""

    package_name: str = Field(min_length=1, max_length=256)
    module_name: str = Field(min_length=1, max_length=256)


class PluginManualInstallRequest(BaseModel):
    """Manual plugin install request payload."""

    requirement: str = Field(min_length=1, max_length=512)
    module_name: str | None = Field(default=None, max_length=256)


class PluginPackageUpdateRequest(BaseModel):
    """Installed plugin package update request payload."""

    package_name: str = Field(min_length=1, max_length=256)


class PluginUninstallRequest(BaseModel):
    """Plugin uninstall request payload."""

    remove_config: bool = False


class OrphanPluginConfigItem(BaseModel):
    """One orphaned plugin config item."""

    section: str
    module_name: str | None = None
    has_section: bool
    reason: str


class OrphanPluginConfigResponse(BaseModel):
    """Preview or cleanup result for orphaned plugin config items."""

    items: list[OrphanPluginConfigItem]


class PluginStoreTaskItem(BaseModel):
    """Plugin store task item returned to the Web UI."""

    task_id: str
    title: str
    status: str
    logs: str
    error: str | None = None
    result: dict[str, object] = {}
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class OperationStatusResponse(BaseModel):
    status: str = "ok"
    detail: str | None = None


class PluginConfigResponse(BaseModel):
    modules: list["PluginConfigModuleItem"]
    dirs: list["PluginConfigDirItem"]


class PluginSettingFieldItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    label: str
    type: str
    editor: str = "readonly"
    item_type: str | None = None
    key_type: str | None = None
    schema_: object | None = Field(default=None, alias="schema")
    default: object | None
    help: str
    choices: list[object] = []
    base_value: object | None = None
    current_value: object | None = None
    local_value: object | None = None
    value_source: str = "default"
    global_key: str | None = None
    has_local_override: bool = False
    allows_null: bool = False
    editable: bool = False
    type_category: str = "unsupported"
    order: int = 99
    secret: bool = False


class PluginSettingsResponse(BaseModel):
    module_name: str
    section: str
    legacy_flatten: bool = False
    config_source: str = "none"
    has_config_model: bool = False
    fields: list[PluginSettingFieldItem]


class PluginRawSettingsResponse(BaseModel):
    module_name: str
    section: str
    text: str


class PluginSettingsUpdateRequest(BaseModel):
    values: dict[str, object | None]
    clear: list[str] = []


class PluginSettingsRawUpdateRequest(BaseModel):
    text: str


class PluginSettingsRawValidationResponse(BaseModel):
    valid: bool
    message: str | None = None
    line: int | None = None
    column: int | None = None


class PluginConfigRequest(BaseModel):
    modules: list[str]
    dirs: list[str]


class AdapterConfigItem(BaseModel):
    name: str
    is_loaded: bool
    is_importable: bool


class AdapterConfigResponse(BaseModel):
    modules: list[AdapterConfigItem]


class AdapterConfigRequest(BaseModel):
    modules: list[str]


class PluginConfigModuleItem(BaseModel):
    name: str
    is_loaded: bool
    is_importable: bool


class PluginConfigDirItem(BaseModel):
    path: str
    exists: bool
    is_loaded: bool


class DriverConfigItem(BaseModel):
    name: str
    is_active: bool


class DriverConfigResponse(BaseModel):
    builtin: list[DriverConfigItem]


class DriverConfigRequest(BaseModel):
    builtin: list[str]


class UserLevelItem(BaseModel):
    user_id: str
    group_id: str
    level: int


class UpdateLevelRequest(BaseModel):
    level: int = Field(ge=0, le=4)


class DataUpdateRequest(BaseModel):
    values: dict[str, object | None]

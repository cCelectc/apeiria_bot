"""Pydantic request/response schemas for Web UI API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Credentials used by the Web UI login endpoint."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class WebUIPrincipalResponse(BaseModel):
    """Authenticated Web UI user information."""

    user_id: str
    username: str


class WebUILocaleItem(BaseModel):
    code: str
    label: str


class WebUIBootstrapResponse(BaseModel):
    principal: WebUIPrincipalResponse
    account: "WebUIAccountItem"
    locales: list[WebUILocaleItem] = []
    preferred_home: str = "/dashboard"
    frontend_workspace: str | None = None


class LoginResponse(BaseModel):
    """Successful login response."""

    principal: WebUIPrincipalResponse


class RegisterResponse(BaseModel):
    """Generic status response returned by legacy auth endpoints."""

    status: str = "ok"
    detail: str | None = None


class WebUIAccountItem(BaseModel):
    """Stored Web UI account information returned to account managers."""

    user_id: str
    username: str
    is_disabled: bool = False
    last_login_at: str | None = None
    password_changed_at: str | None = None


class PasswordChangeRequest(BaseModel):
    """Request payload used to rotate the current account password."""

    current_password: str | None = Field(default=None, min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AccountCreateRequest(BaseModel):
    """Request payload used to create one managed account."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    actor_password: str = Field(min_length=8, max_length=128)


class AccountDisableRequest(BaseModel):
    """Request payload used to enable or disable one managed account."""

    is_disabled: bool
    actor_password: str = Field(min_length=8, max_length=128)


class AccountDeleteRequest(BaseModel):
    """Request payload used to delete one managed account."""

    actor_password: str = Field(min_length=8, max_length=128)


class AccountPasswordResetRequest(BaseModel):
    """Request payload used to reset another account password."""

    new_password: str = Field(min_length=8, max_length=128)
    actor_password: str = Field(min_length=8, max_length=128)


class SessionRefreshResponse(BaseModel):
    """Response used when the current session must rotate in place."""

    status: str = "ok"
    detail: str | None = None
    principal: WebUIPrincipalResponse


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


class DataUpdateRequest(BaseModel):
    values: dict[str, object | None]

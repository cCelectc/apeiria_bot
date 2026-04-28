from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_SRC_ROOT = REPO_ROOT / "web" / "src"
REMOVED_BROWSER_API_BUCKET = WEB_SRC_ROOT / "api" / "index.ts"
REMOVED_AI_API_BUCKET = WEB_SRC_ROOT / "api" / "ai.ts"
AI_RESOURCE_API_MODULES = (
    WEB_SRC_ROOT / "api" / "ai" / "bootstrap.ts",
    WEB_SRC_ROOT / "api" / "ai" / "futureTasks.ts",
    WEB_SRC_ROOT / "api" / "ai" / "index.ts",
    WEB_SRC_ROOT / "api" / "ai" / "memories.ts",
    WEB_SRC_ROOT / "api" / "ai" / "models.ts",
    WEB_SRC_ROOT / "api" / "ai" / "personas.ts",
    WEB_SRC_ROOT / "api" / "ai" / "relationships.ts",
    WEB_SRC_ROOT / "api" / "ai" / "sessions.ts",
    WEB_SRC_ROOT / "api" / "ai" / "sources.ts",
    WEB_SRC_ROOT / "api" / "ai" / "tools.ts",
    WEB_SRC_ROOT / "api" / "ai" / "types.ts",
)
ADAPTER_API_MODULE = WEB_SRC_ROOT / "api" / "adapters.ts"
CHAT_VIEW = WEB_SRC_ROOT / "views" / "ChatView.vue"
CHAT_WORKFLOW_MODULES = (
    WEB_SRC_ROOT / "views" / "chat" / "ChatMessageList.vue",
    WEB_SRC_ROOT / "views" / "chat" / "composer.ts",
    WEB_SRC_ROOT / "views" / "chat" / "mediaPreview.ts",
    WEB_SRC_ROOT / "views" / "chat" / "messageDisplay.ts",
    WEB_SRC_ROOT / "views" / "chat" / "sessionState.ts",
    WEB_SRC_ROOT / "views" / "chat" / "transport.ts",
    WEB_SRC_ROOT / "views" / "chat" / "useChatComposer.ts",
)
CORE_VIEW = WEB_SRC_ROOT / "views" / "CoreView.vue"
CORE_WORKFLOW_MODULES = (
    WEB_SRC_ROOT / "views" / "core" / "AdapterManagementPanel.vue",
    WEB_SRC_ROOT / "views" / "core" / "adapterStatus.ts",
    WEB_SRC_ROOT / "views" / "core" / "routeState.ts",
    WEB_SRC_ROOT / "views" / "core" / "useAdapterManagement.ts",
)
PLUGINS_VIEW = WEB_SRC_ROOT / "views" / "PluginsView.vue"
PLUGIN_WORKFLOW_MODULES = (
    WEB_SRC_ROOT / "views" / "plugins" / "actions.ts",
    WEB_SRC_ROOT / "views" / "plugins" / "display.ts",
    WEB_SRC_ROOT / "views" / "plugins" / "filters.ts",
    WEB_SRC_ROOT / "views" / "plugins" / "install.ts",
    WEB_SRC_ROOT / "views" / "plugins" / "readme.ts",
    WEB_SRC_ROOT / "views" / "plugins" / "tasks.ts",
    WEB_SRC_ROOT / "views" / "plugins" / "usePluginActions.ts",
    WEB_SRC_ROOT / "views" / "plugins" / "usePluginInstallTasks.ts",
    WEB_SRC_ROOT / "views" / "plugins" / "usePluginListState.ts",
    WEB_SRC_ROOT / "views" / "plugins" / "usePluginReadmeDialog.ts",
    WEB_SRC_ROOT / "views" / "plugins" / "usePluginSettingsDialog.ts",
    WEB_SRC_ROOT / "views" / "plugins" / "usePluginUpdateChecks.ts",
)
PERMISSIONS_VIEW = WEB_SRC_ROOT / "views" / "PermissionsView.vue"
PERMISSION_WORKFLOW_MODULES = (
    WEB_SRC_ROOT / "views" / "permissions" / "filters.ts",
    WEB_SRC_ROOT / "views" / "permissions" / "options.ts",
    WEB_SRC_ROOT / "views" / "permissions" / "usePermissionPluginPerspective.ts",
    WEB_SRC_ROOT / "views" / "permissions" / "usePermissionRouteState.ts",
    WEB_SRC_ROOT / "views" / "permissions" / "usePermissionRules.ts",
    WEB_SRC_ROOT / "views" / "permissions" / "usePermissionUserPerspective.ts",
)
TARGET_ROUTE_VIEW_LINE_LIMITS = {
    CHAT_VIEW: 1000,
    CORE_VIEW: 1000,
    PERMISSIONS_VIEW: 1000,
    PLUGINS_VIEW: 1700,
}
FORBIDDEN_IMPORT_PATTERN = re.compile(r"""from\s+['"]@/api(?:/index)?['"]""")


def test_browser_side_catch_all_api_bucket_is_removed() -> None:
    assert not REMOVED_BROWSER_API_BUCKET.exists()


def test_browser_side_ai_api_is_resource_scoped() -> None:
    assert not REMOVED_AI_API_BUCKET.exists()

    missing_modules = tuple(
        str(path.relative_to(REPO_ROOT))
        for path in AI_RESOURCE_API_MODULES
        if not path.is_file()
    )
    assert not missing_modules


def test_browser_side_adapter_api_module_exists() -> None:
    assert ADAPTER_API_MODULE.is_file()


def test_browser_side_modules_do_not_import_removed_api_bucket() -> None:
    violations: list[str] = []

    for path in sorted(_iter_browser_source_files()):
        text = path.read_text(encoding="utf-8")
        if FORBIDDEN_IMPORT_PATTERN.search(text):
            violations.append(str(path.relative_to(REPO_ROOT)))

    message = "browser-side modules importing removed @/api bucket:\n" + "\n".join(
        violations,
    )
    assert not violations, message


def test_browser_side_modules_do_not_import_ai_api_bucket() -> None:
    violations: list[str] = []
    forbidden_pattern = re.compile(r"""from\s+['"]@/api/ai['"]""")

    for path in sorted(_iter_browser_source_files()):
        if path in AI_RESOURCE_API_MODULES:
            continue
        text = path.read_text(encoding="utf-8")
        if forbidden_pattern.search(text):
            violations.append(str(path.relative_to(REPO_ROOT)))

    message = "browser-side modules importing removed @/api/ai bucket:\n" + "\n".join(
        violations,
    )
    assert not violations, message


def test_chat_view_delegates_focused_workflow_modules() -> None:
    for path in CHAT_WORKFLOW_MODULES:
        assert path.exists(), f"missing chat workflow module: {path}"

    text = CHAT_VIEW.read_text(encoding="utf-8")

    for module_path in (
        "@/views/chat/ChatMessageList.vue",
        "@/views/chat/mediaPreview",
        "@/views/chat/messageDisplay",
        "@/views/chat/sessionState",
        "@/views/chat/transport",
        "@/views/chat/useChatComposer",
    ):
        assert module_path in text


def test_core_view_delegates_adapter_management_modules() -> None:
    for path in CORE_WORKFLOW_MODULES:
        assert path.exists(), f"missing core workflow module: {path}"

    view_text = CORE_VIEW.read_text(encoding="utf-8")
    panel_text = (
        WEB_SRC_ROOT / "views" / "core" / "AdapterManagementPanel.vue"
    ).read_text(encoding="utf-8")
    state_text = (
        WEB_SRC_ROOT / "views" / "core" / "useAdapterManagement.ts"
    ).read_text(encoding="utf-8")

    assert "@/views/core/AdapterManagementPanel.vue" in view_text
    assert "@/views/core/routeState" in view_text
    assert "@/views/core/useAdapterManagement" in panel_text
    assert "@/views/core/adapterStatus" in state_text


def test_plugins_view_delegates_focused_workflow_modules() -> None:
    for path in PLUGIN_WORKFLOW_MODULES:
        assert path.exists(), f"missing plugin workflow module: {path}"

    text = PLUGINS_VIEW.read_text(encoding="utf-8")

    for module_path in (
        "@/views/plugins/display",
        "@/views/plugins/usePluginActions",
        "@/views/plugins/usePluginInstallTasks",
        "@/views/plugins/usePluginListState",
        "@/views/plugins/usePluginReadmeDialog",
        "@/views/plugins/usePluginSettingsDialog",
        "@/views/plugins/usePluginUpdateChecks",
    ):
        assert module_path in text


def test_permissions_view_delegates_focused_workflow_modules() -> None:
    for path in PERMISSION_WORKFLOW_MODULES:
        assert path.exists(), f"missing permission workflow module: {path}"

    text = PERMISSIONS_VIEW.read_text(encoding="utf-8")

    for module_path in (
        "@/views/permissions/filters",
        "@/views/permissions/options",
        "@/views/permissions/usePermissionPluginPerspective",
        "@/views/permissions/usePermissionRouteState",
        "@/views/permissions/usePermissionRules",
        "@/views/permissions/usePermissionUserPerspective",
    ):
        assert module_path in text


def test_target_route_views_stay_within_composition_shell_size() -> None:
    violations = []

    for path, limit in TARGET_ROUTE_VIEW_LINE_LIMITS.items():
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > limit:
            violations.append(
                f"{path.relative_to(REPO_ROOT)} has {line_count} lines, limit {limit}",
            )

    message = "target route views exceeding composition-shell limits:\n" + "\n".join(
        violations,
    )
    assert not violations, message


def _iter_browser_source_files() -> list[Path]:
    return [
        *WEB_SRC_ROOT.rglob("*.ts"),
        *WEB_SRC_ROOT.rglob("*.vue"),
    ]

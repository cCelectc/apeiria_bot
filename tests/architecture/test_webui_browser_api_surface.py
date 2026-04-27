from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_SRC_ROOT = REPO_ROOT / "web" / "src"
REMOVED_BROWSER_API_BUCKET = WEB_SRC_ROOT / "api" / "index.ts"
CHAT_VIEW = WEB_SRC_ROOT / "views" / "ChatView.vue"
CHAT_WORKFLOW_MODULES = (
    WEB_SRC_ROOT / "views" / "chat" / "composer.ts",
    WEB_SRC_ROOT / "views" / "chat" / "mediaPreview.ts",
    WEB_SRC_ROOT / "views" / "chat" / "messageDisplay.ts",
    WEB_SRC_ROOT / "views" / "chat" / "sessionState.ts",
    WEB_SRC_ROOT / "views" / "chat" / "transport.ts",
)
PLUGINS_VIEW = WEB_SRC_ROOT / "views" / "PluginsView.vue"
PLUGIN_WORKFLOW_MODULES = (
    WEB_SRC_ROOT / "views" / "plugins" / "display.ts",
    WEB_SRC_ROOT / "views" / "plugins" / "filters.ts",
    WEB_SRC_ROOT / "views" / "plugins" / "readme.ts",
    WEB_SRC_ROOT / "views" / "plugins" / "tasks.ts",
)
FORBIDDEN_IMPORT_PATTERN = re.compile(
    r"""from\s+['"]@/api(?:/index)?['"]"""
)


def test_browser_side_catch_all_api_bucket_is_removed() -> None:
    assert not REMOVED_BROWSER_API_BUCKET.exists()


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


def test_chat_view_delegates_focused_workflow_modules() -> None:
    for path in CHAT_WORKFLOW_MODULES:
        assert path.exists(), f"missing chat workflow module: {path}"

    text = CHAT_VIEW.read_text(encoding="utf-8")

    for module_path in (
        "@/views/chat/composer",
        "@/views/chat/mediaPreview",
        "@/views/chat/messageDisplay",
        "@/views/chat/sessionState",
        "@/views/chat/transport",
    ):
        assert module_path in text


def test_plugins_view_delegates_focused_workflow_modules() -> None:
    for path in PLUGIN_WORKFLOW_MODULES:
        assert path.exists(), f"missing plugin workflow module: {path}"

    text = PLUGINS_VIEW.read_text(encoding="utf-8")

    for module_path in (
        "@/views/plugins/display",
        "@/views/plugins/filters",
        "@/views/plugins/readme",
        "@/views/plugins/tasks",
    ):
        assert module_path in text


def _iter_browser_source_files() -> list[Path]:
    return [
        *WEB_SRC_ROOT.rglob("*.ts"),
        *WEB_SRC_ROOT.rglob("*.vue"),
    ]

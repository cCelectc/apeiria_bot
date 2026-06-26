from __future__ import annotations

from arclet.alconna import Args, CommandMeta
from nonebot.adapters import Event  # noqa: TC002
from nonebot_plugin_alconna import Alconna, Match, on_alconna

from apeiria.plugin.manager import set_plugin_state
from apeiria.plugin.scanner import PluginManifest, scan_plugins

from .presenter import render_block, render_list_block
from .utils import ensure_owner_message

_plugins = on_alconna(
    Alconna("plugins", meta=CommandMeta(description="查看插件列表")),
    use_cmd_start=True,
    priority=5,
    block=True,
)

_plugin = on_alconna(
    Alconna(
        "plugin",
        Args["action", str],
        Args["plugin_name?", str],
        meta=CommandMeta(description="管理单个插件"),
    ),
    use_cmd_start=True,
    priority=5,
    block=True,
)


@_plugins.handle()
async def handle_plugins(event: Event) -> None:
    owner_error = ensure_owner_message(event)
    if owner_error:
        await _plugins.finish(owner_error)

    items = scan_plugins()
    if not items:
        await _plugins.finish("暂无已加载插件")

    enabled_count = sum(1 for p in items if p.enabled)
    lines = [
        f"- [{p.source}] {p.name} ({'启用' if p.enabled else '禁用'})" for p in items
    ]
    summary = (
        f"共 {len(items)} 个 | 启用 {enabled_count} | 禁用 {len(items) - enabled_count}"
    )
    await _plugins.finish(
        render_list_block(
            "插件列表",
            lines,
            summary=summary,
        )
    )


@_plugin.handle()
async def handle_plugin(
    event: Event,
    action: Match[str],
    plugin_name: Match[str],
) -> None:
    owner_error = ensure_owner_message(event)
    if owner_error:
        await _plugin.finish(owner_error)

    selected_action = action.result.strip().lower()
    if selected_action not in {"info", "enable", "disable"}:
        await _plugin.finish("操作无效，可选: info / enable / disable")

    if not plugin_name.available:
        await _plugin.finish("用法: /plugin (info|enable|disable) <插件名>")

    query = plugin_name.result.strip()
    matched = _find_plugin(query)

    if matched is None:
        await _plugin.finish(f"未找到插件: {query}")

    if selected_action == "info":
        await _plugin.finish(_render_info(matched))

    enabled = selected_action == "enable"
    set_plugin_state(matched.name, enabled)
    action_chinese = "启用" if enabled else "禁用"
    await _plugin.finish(f"已{action_chinese}插件: {matched.name}")


def _find_plugin(query: str) -> PluginManifest | None:
    normalized = query.strip().lower()
    for p in scan_plugins():
        if normalized in (p.name.lower(), normalized):
            return p
    return None


def _render_info(p: PluginManifest) -> str:
    return render_block(
        "插件详情",
        [
            ("名称", p.name),
            ("来源", p.source),
            ("模块", p.path_or_module),
            ("状态", "启用" if p.enabled else "禁用"),
        ],
    )

from __future__ import annotations

from arclet.alconna import Args, CommandMeta
from nonebot.adapters import Event  # noqa: TC002
from nonebot_plugin_alconna import Alconna, Match, on_alconna

from apeiria.plugin.adapter_manager import set_adapter_state
from apeiria.plugin.adapter_scanner import AdapterManifest, scan_adapters

from .presenter import render_block, render_list_block
from .utils import ensure_owner_message

_adapters = on_alconna(
    Alconna("adapters", meta=CommandMeta(description="查看适配器列表")),
    use_cmd_start=True,
    priority=5,
    block=True,
)

_adapter = on_alconna(
    Alconna(
        "adapter",
        Args["action", str],
        Args["adapter_name?", str],
        meta=CommandMeta(description="管理单个适配器"),
    ),
    use_cmd_start=True,
    priority=5,
    block=True,
)


@_adapters.handle()
async def handle_adapters(event: Event) -> None:
    owner_error = ensure_owner_message(event)
    if owner_error:
        await _adapters.finish(owner_error)

    items = scan_adapters()
    if not items:
        await _adapters.finish("暂无已加载适配器")

    enabled_count = sum(1 for a in items if a.enabled)
    lines = [
        f"- [{a.source}] {a.name} ({'启用' if a.enabled else '禁用'})" for a in items
    ]
    summary = (
        f"共 {len(items)} 个 | 启用 {enabled_count} | 禁用 {len(items) - enabled_count}"
    )
    await _adapters.finish(
        render_list_block(
            "适配器列表",
            lines,
            summary=summary,
        )
    )


@_adapter.handle()
async def handle_adapter(
    event: Event,
    action: Match[str],
    adapter_name: Match[str],
) -> None:
    owner_error = ensure_owner_message(event)
    if owner_error:
        await _adapter.finish(owner_error)

    selected_action = action.result.strip().lower()
    if selected_action not in {"info", "enable", "disable"}:
        await _adapter.finish("操作无效，可选: info / enable / disable")

    if not adapter_name.available:
        await _adapter.finish("用法: /adapter (info|enable|disable) <适配器名>")

    query = adapter_name.result.strip()
    matched = _find_adapter(query)

    if matched is None:
        await _adapter.finish(f"未找到适配器: {query}")

    if selected_action == "info":
        await _adapter.finish(_render_info(matched))

    enabled = selected_action == "enable"
    set_adapter_state(matched.name, enabled)
    action_chinese = "启用" if enabled else "禁用"
    await _adapter.finish(f"已{action_chinese}适配器: {matched.name}")


def _find_adapter(query: str) -> AdapterManifest | None:
    normalized = query.strip().lower()
    for a in scan_adapters():
        if normalized in (a.name.lower(), a.module_name.lower()):
            return a
    return None


def _render_info(a: AdapterManifest) -> str:
    return render_block(
        "适配器详情",
        [
            ("名称", a.name),
            ("来源", a.source),
            ("模块", a.module_name),
            ("状态", a.enabled),
        ],
    )

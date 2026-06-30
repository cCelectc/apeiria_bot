from __future__ import annotations

from arclet.alconna import Args, CommandMeta
from nonebot.adapters import Event  # noqa: TC002
from nonebot_plugin_alconna import Alconna, Match, on_alconna
from sqlalchemy import select

from apeiria.db.engine import get_db
from apeiria.db.models.access import AccessRule

from .utils import ensure_owner_message

_USAGE_ADD = "用法见帮助: /access add allow|deny user|group ID 插件名"
_USAGE_RM = "用法见帮助: /access remove user|group ID 插件名"

_access = on_alconna(
    Alconna(
        "access",
        Args["action", str],
        Args["arg1?", str],
        Args["arg2?", str],
        Args["arg3?", str],
        Args["arg4?", str],
        Args["arg5?", str],
        meta=CommandMeta(description="管理权限规则"),
    ),
    use_cmd_start=True,
    priority=5,
    block=True,
)


@_access.handle()
async def handle_access(  # noqa: PLR0913
    event: Event,
    action: Match[str],
    arg1: Match[str],
    arg2: Match[str],
    arg3: Match[str],
    arg4: Match[str],
    arg5: Match[str],
) -> None:
    owner_error = ensure_owner_message(event)
    if owner_error:
        await _access.finish(owner_error)

    selected = action.result.strip().lower()

    if selected == "list":
        await _access.finish(await _list_rules())

    if selected == "add":
        if not all((arg1.available, arg2.available, arg3.available, arg4.available)):
            await _access.finish(_USAGE_ADD)
            return
        await _access.finish(
            await _add_rule(
                arg1.result,
                arg2.result,
                arg3.result,
                arg4.result,
                arg5.result if arg5.available else "0",
            )
        )

    if selected == "remove":
        if not all((arg1.available, arg2.available, arg3.available)):
            await _access.finish(_USAGE_RM)
            return
        await _access.finish(await _del_rule(arg1.result, arg2.result, arg3.result))

    await _access.finish("操作无效，可选: list / add / remove")


async def _list_rules() -> str:
    db = get_db()
    async with db.gate.read() as sess:
        rules = list((await sess.execute(select(AccessRule))).scalars().all())
    if not rules:
        return "暂无权限规则"
    lines = [
        f"- [{r.action}] {r.subject_type}:{r.subject_id}"
        f" → {r.plugin_name or '全局'} p={r.priority}"
        for r in rules
    ]
    return "权限规则:\n\n" + "\n".join(lines)


async def _add_rule(
    effect: str,
    subject_type: str,
    subject_id: str,
    plugin_query: str,
    priority: str = "0",
) -> str:
    normalized_effect = effect.strip().lower()
    normalized_type = subject_type.strip().lower()
    if normalized_effect not in {"allow", "deny"}:
        return _USAGE_ADD
    if normalized_type not in {"user", "group"}:
        return _USAGE_ADD

    try:
        priority_int = int(priority)
    except (ValueError, TypeError):
        priority_int = 0

    q = plugin_query.strip().lower()
    plugin_name = None if q == "global" else plugin_query.strip()
    db = get_db()
    async with db.gate.write() as sess:
        rule = AccessRule(
            subject_type=normalized_type,
            subject_id=subject_id.strip(),
            plugin_name=plugin_name,
            action=normalized_effect,
            priority=priority_int,
        )
        sess.add(rule)
        await sess.flush()
    target = plugin_name or "全局"
    return f"已添加: {normalized_effect} {normalized_type}:{subject_id} → {target}"


async def _del_rule(
    subject_type: str,
    subject_id: str,
    plugin_query: str,
) -> str:
    normalized_type = subject_type.strip().lower()
    if normalized_type not in {"user", "group"}:
        return _USAGE_RM

    q = plugin_query.strip().lower()
    plugin_name = None if q == "global" else plugin_query.strip()
    db = get_db()
    async with db.gate.write() as sess:
        stmt = select(AccessRule).where(
            AccessRule.subject_type == normalized_type,
            AccessRule.subject_id == subject_id.strip(),
            AccessRule.plugin_name == plugin_name,
        )
        rules = list((await sess.execute(stmt)).scalars().all())
        if not rules:
            return "未找到匹配的权限规则"
        for rule in rules:
            await sess.delete(rule)
        await sess.flush()
    return f"已移除 {len(rules)} 条权限规则"

# pyright: reportAttributeAccessIssue=false
from __future__ import annotations

import nonebot
from nonebot.adapters import Event  # noqa: TC002


def resolve_plugin_query(
    query: str,
    *,
    allow_fuzzy: bool,
) -> tuple[nonebot.plugin.Plugin | None, list[str]]:
    normalized = query.strip().lower()
    if not normalized:
        return None, []

    exact_matches: list[nonebot.plugin.Plugin] = []
    fuzzy_matches: list[nonebot.plugin.Plugin] = []
    for plugin in nonebot.get_loaded_plugins():
        candidates = [
            plugin.module_name.lower(),
            plugin.id_.lower(),
        ]
        if normalized in candidates:
            exact_matches.append(plugin)
            continue
        if any(normalized in candidate for candidate in candidates):
            fuzzy_matches.append(plugin)

    resolved: nonebot.plugin.Plugin | None = None
    candidates: list[str] = []
    if len(exact_matches) == 1:
        resolved = exact_matches[0]
    elif exact_matches:
        candidates = sorted({f"{p.id_} ({p.module_name})" for p in exact_matches})
    elif len(fuzzy_matches) == 1 and allow_fuzzy:
        resolved = fuzzy_matches[0]
    elif fuzzy_matches:
        candidates = sorted({f"{p.id_} ({p.module_name})" for p in fuzzy_matches})
    return resolved, candidates


def is_owner_event(event: Event) -> bool:
    try:
        user_id = str(event.get_user_id())
    except Exception:  # noqa: BLE001
        return False
    superusers = nonebot.get_driver().config.superusers
    return user_id in superusers or any(
        isinstance(s, str) and s.endswith(f":{user_id}") for s in superusers
    )


def ensure_owner_message(event: Event) -> str | None:
    if is_owner_event(event):
        return None
    return "仅限超级用户使用"

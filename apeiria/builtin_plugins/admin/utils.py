"""Common utilities for the owner admin plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nonebot
from nonebot.adapters import Event  # noqa: TC002

from apeiria.bot.superuser import is_superuser_id
from apeiria.i18n import t
from apeiria.plugins.management import plugin_management_service
from apeiria.utils.plugin_introspection import get_plugin_name

if TYPE_CHECKING:
    from nonebot.plugin import Plugin


def resolve_plugin_query(
    query: str,
    *,
    allow_fuzzy: bool,
) -> tuple[Plugin | None, list[str]]:
    """Resolve one plugin query and return ambiguity candidates when needed."""
    normalized = query.strip().lower()
    if not normalized:
        return None, []

    exact_matches: list[Plugin] = []
    fuzzy_matches: list[Plugin] = []
    for plugin in nonebot.get_loaded_plugins():
        display_name = get_plugin_name(plugin)
        candidates = [
            plugin.module_name.lower(),
            plugin.id_.lower(),
            display_name.lower(),
        ]
        if normalized in candidates:
            exact_matches.append(plugin)
            continue
        if any(normalized in candidate for candidate in candidates):
            fuzzy_matches.append(plugin)

    resolved: Plugin | None = None
    candidates: list[str] = []
    if len(exact_matches) == 1:
        resolved = exact_matches[0]
    elif exact_matches:
        candidates = _format_plugin_candidates(exact_matches)
    elif len(fuzzy_matches) == 1 and allow_fuzzy:
        resolved = fuzzy_matches[0]
    elif fuzzy_matches:
        candidates = _format_plugin_candidates(fuzzy_matches)
    return resolved, candidates


async def resolve_plugin_catalog_query(
    query: str,
    *,
    allow_fuzzy: bool,
) -> tuple[Any | None, list[str]]:
    """Resolve one plugin query from the plugin catalog."""
    normalized = query.strip().lower()
    if not normalized:
        return None, []

    exact_matches: list[Any] = []
    fuzzy_matches: list[Any] = []
    for item in await plugin_management_service.list_plugins():
        candidates = [
            item.descriptor.module_name.lower(),
            item.descriptor.name.lower(),
        ]
        if normalized in candidates:
            exact_matches.append(item)
            continue
        if any(normalized in candidate for candidate in candidates):
            fuzzy_matches.append(item)

    resolved: Any | None = None
    candidates: list[str] = []
    if len(exact_matches) == 1:
        resolved = exact_matches[0]
    elif exact_matches:
        candidates = _format_catalog_candidates(exact_matches)
    elif len(fuzzy_matches) == 1 and allow_fuzzy:
        resolved = fuzzy_matches[0]
    elif fuzzy_matches:
        candidates = _format_catalog_candidates(fuzzy_matches)
    return resolved, candidates


def is_owner_event(event: Event) -> bool:
    """Return whether the current event user is a configured superuser."""
    try:
        user_id = event.get_user_id()
    except Exception:  # noqa: BLE001
        return False
    return is_superuser_id(str(user_id))


def ensure_owner_message(event: Event) -> str | None:
    """Return an owner-only message when the caller lacks access."""
    if is_owner_event(event):
        return None
    return t("admin.owner_only")


def _format_plugin_candidates(plugins: list[Plugin]) -> list[str]:
    labels = {_format_plugin_candidate(plugin) for plugin in plugins}
    return sorted(labels, key=str.lower)


def _format_plugin_candidate(plugin: Plugin) -> str:
    name = get_plugin_name(plugin)
    if name == plugin.module_name:
        return plugin.module_name
    return f"{name} ({plugin.module_name})"


def _format_catalog_candidates(plugins: list[Any]) -> list[str]:
    labels = {
        (
            item.descriptor.module_name
            if item.descriptor.name == item.descriptor.module_name
            else f"{item.descriptor.name} ({item.descriptor.module_name})"
        )
        for item in plugins
    }
    return sorted(labels, key=str.lower)

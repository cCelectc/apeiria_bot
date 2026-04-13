"""Owner-facing configuration summary commands."""

from __future__ import annotations

from arclet.alconna import Args, CommandMeta
from nonebot.adapters import Event  # noqa: TC002
from nonebot_plugin_alconna import Alconna, Match, on_alconna

from apeiria.app.plugins import (
    PluginSettingsNotConfigurableError,
    plugin_config_view_service,
)
from apeiria.shared.i18n import t

from .presenter import render_list_block, summarize_value
from .utils import ensure_owner_message, resolve_plugin_catalog_query

_config = on_alconna(
    Alconna(
        "config",
        Args["scope", str],
        Args["target?", str],
        meta=CommandMeta(description=t("admin.command.config")),
    ),
    use_cmd_start=True,
    priority=5,
    block=True,
)


@_config.handle()
async def handle_config(
    event: Event,
    scope: Match[str],
    target: Match[str],
) -> None:
    owner_error = ensure_owner_message(event)
    if owner_error:
        await _config.finish(owner_error)

    selected_scope = scope.result.strip().lower()
    if selected_scope == "core":
        await _config.finish(_render_core_settings())

    if selected_scope != "plugin":
        await _config.finish(t("admin.config.invalid_scope"))

    if not target.available:
        await _config.finish(t("admin.config.plugin_usage"))

    plugin, candidates = await resolve_plugin_catalog_query(
        target.result,
        allow_fuzzy=True,
    )
    if candidates:
        await _config.finish(
            t(
                "admin.plugin.ambiguous",
                name=target.result,
                candidates=", ".join(candidates),
            )
        )
    if plugin is None:
        await _config.finish(t("admin.plugin.not_found", name=target.result))

    await _config.finish(_render_plugin_settings(plugin.module_name, plugin.name))


def _render_core_settings() -> str:
    state = plugin_config_view_service.get_core_settings()
    items = [
        f"- {field.key} = {summarize_value(field.key, field.current_value)} "
        f"({_source_label(field.value_source)})"
        for field in state.fields
    ]
    return render_list_block(
        t("admin.config.core_title"),
        items,
        summary=t("admin.config.core_summary", count=len(items)),
        empty_message=t("admin.config.empty"),
    )


def _render_plugin_settings(module_name: str, plugin_name: str) -> str:
    try:
        state = plugin_config_view_service.get_plugin_settings(module_name)
    except PluginSettingsNotConfigurableError:
        return t("admin.config.plugin_not_configurable", name=plugin_name)
    except ValueError:
        return t("admin.config.plugin_not_configurable", name=plugin_name)
    if not state.has_config_model:
        return t("admin.config.plugin_not_configurable", name=plugin_name)

    items = [
        f"- {field.key} = {summarize_value(field.key, field.current_value)} "
        f"({_source_label(field.value_source)})"
        for field in state.fields
    ]
    return render_list_block(
        t("admin.config.plugin_title", name=plugin_name),
        items,
        summary=t(
            "admin.config.plugin_summary",
            section=state.section,
            count=len(items),
        ),
        empty_message=t("admin.config.empty"),
    )


def _source_label(source: str) -> str:
    mapping = {
        "default": t("admin.config.source_default"),
        "env": t("admin.config.source_env"),
        "legacy_global": t("admin.config.source_legacy_global"),
        "plugin_section": t("admin.config.source_plugin_section"),
        "built_in": t("admin.config.source_builtin"),
    }
    return mapping.get(source, source)


def render_plugin_settings_summary(module_name: str, plugin_name: str) -> str:
    """Public helper for showing plugin configuration summaries."""
    return _render_plugin_settings(module_name, plugin_name)

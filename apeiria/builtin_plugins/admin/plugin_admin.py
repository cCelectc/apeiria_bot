"""Owner-facing plugin management commands."""

from __future__ import annotations

from arclet.alconna import Args, CommandMeta
from nonebot.adapters import Event  # noqa: TC002
from nonebot_plugin_alconna import Alconna, Match, on_alconna

from apeiria.exceptions import ProtectedPluginError, ResourceNotFoundError
from apeiria.i18n import t
from apeiria.plugins import (
    PluginCatalogEntry,
    PluginSettingsNotConfigurableError,
    config_query_service,
    plugin_governance_service,
)

from .config_view import render_plugin_settings_summary
from .presenter import render_block, render_list_block
from .utils import ensure_owner_message, resolve_plugin_catalog_query

_plugins = on_alconna(
    Alconna("plugins", meta=CommandMeta(description=t("admin.command.plugins"))),
    use_cmd_start=True,
    priority=5,
    block=True,
)

_plugin = on_alconna(
    Alconna(
        "plugin",
        Args["action", str],
        Args["plugin_name?", str],
        meta=CommandMeta(description=t("admin.command.plugin")),
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

    items = await _list_visible_plugins()
    if not items:
        await _plugins.finish(
            render_list_block(
                t("admin.plugins.title"),
                [],
                empty_message=t("admin.plugins.empty"),
            )
        )

    enabled_count = sum(1 for item in items if item.governance_state.is_global_enabled)
    protected_count = sum(1 for item in items if item.governance_state.is_protected)
    lines = [_format_plugin_summary_line(item) for item in items]
    await _plugins.finish(
        render_list_block(
            t("admin.plugins.title"),
            lines,
            summary=t(
                "admin.plugins.summary",
                count=len(items),
                enabled=enabled_count,
                disabled=len(items) - enabled_count,
                protected=protected_count,
            ),
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
    if selected_action not in {"info", "enable", "disable", "configs"}:
        await _plugin.finish(t("admin.plugin.invalid_action"))

    if not plugin_name.available:
        await _plugin.finish(t("admin.plugin.usage"))

    item, candidates = await resolve_plugin_catalog_query(
        plugin_name.result,
        allow_fuzzy=selected_action in {"info", "configs"},
    )
    if candidates:
        await _plugin.finish(
            t(
                "admin.plugin.ambiguous",
                name=plugin_name.result,
                candidates=", ".join(candidates),
            )
        )
    if item is None:
        await _plugin.finish(t("admin.plugin.not_found", name=plugin_name.result))

    module_name = item.descriptor.module_name
    if selected_action == "info":
        await _plugin.finish(await _render_plugin_info(module_name))
    if selected_action == "configs":
        await _plugin.finish(
            render_plugin_settings_summary(module_name, item.descriptor.name)
        )

    await _plugin.finish(
        await _handle_plugin_toggle(
            item,
            selected_action=selected_action,
            raw_query=plugin_name.result,
        )
    )


async def _render_plugin_info(module_name: str) -> str:
    item = await plugin_governance_service.get_plugin(module_name)
    if item is None:
        return t("admin.plugin.not_found", name=module_name)

    try:
        settings = config_query_service.get_plugin_view(module_name)
        configurable = (
            t("admin.common.yes") if settings.has_config_model else t("admin.common.no")
        )
        section = settings.section
    except PluginSettingsNotConfigurableError:
        configurable = t("admin.common.no")
        section = t("admin.common.none")
    except ValueError:
        configurable = t("admin.common.no")
        section = t("admin.common.none")

    return render_block(
        t("admin.plugin.info_title"),
        [
            (t("admin.plugin.field_name"), item.descriptor.name),
            (t("admin.plugin.field_module"), item.descriptor.module_name),
            (t("admin.plugin.field_kind"), item.governance_state.kind),
            (t("admin.plugin.field_source"), item.descriptor.source),
            (t("admin.plugin.field_type"), item.descriptor.plugin_type),
            (
                t("admin.plugin.field_version"),
                item.descriptor.version or t("admin.common.none"),
            ),
            (
                t("admin.plugin.field_author"),
                item.descriptor.author or t("admin.common.none"),
            ),
            (
                t("admin.plugin.field_enabled"),
                t("admin.common.enabled")
                if item.governance_state.is_global_enabled
                else t("admin.common.disabled"),
            ),
            (
                t("admin.plugin.field_protected"),
                item.governance_state.protected_reason or t("admin.common.none"),
            ),
            (
                t("admin.plugin.field_required"),
                ", ".join(item.governance_state.required_plugins)
                or t("admin.common.none"),
            ),
            (
                t("admin.plugin.field_dependents"),
                ", ".join(item.governance_state.dependent_plugins)
                or t("admin.common.none"),
            ),
            (
                t("admin.plugin.field_configurable"),
                configurable,
            ),
            (t("admin.plugin.field_config_section"), section),
        ],
        summary=item.descriptor.description or t("admin.plugin.no_description"),
    )


async def _handle_plugin_toggle(
    item: PluginCatalogEntry,
    *,
    selected_action: str,
    raw_query: str,
) -> str:
    module_name = item.descriptor.module_name
    plugin_name = item.descriptor.name
    try:
        changed = await plugin_governance_service.set_plugin_enabled(
            module_name,
            enabled=selected_action == "enable",
        )
    except ResourceNotFoundError:
        return t("admin.plugin.not_found", name=raw_query)
    except ProtectedPluginError as exc:
        return t("admin.plugin.protected", name=plugin_name, reason=str(exc))

    if not changed:
        key = (
            "admin.plugin.already_enabled"
            if selected_action == "enable"
            else "admin.plugin.already_disabled"
        )
        return t(key, name=plugin_name)

    key = (
        "admin.plugin.enabled"
        if selected_action == "enable"
        else "admin.plugin.disabled"
    )
    return t(key, name=plugin_name)


async def _list_visible_plugins() -> list[PluginCatalogEntry]:
    items = await plugin_governance_service.list_plugins()
    return sorted(
        items,
        key=lambda item: (
            item.descriptor.source,
            item.descriptor.name.lower(),
            item.descriptor.module_name,
        ),
    )


def _format_plugin_summary_line(item: PluginCatalogEntry) -> str:
    status = (
        t("admin.common.enabled")
        if item.governance_state.is_global_enabled
        else t("admin.common.disabled")
    )
    protection = (
        t("admin.common.locked")
        if item.governance_state.is_protected
        else t("admin.common.unlocked")
    )
    return (
        f"- {status} {item.descriptor.name} ({item.descriptor.module_name})"
        f" | {item.descriptor.source} | {item.descriptor.plugin_type}"
        f" | {protection}"
    )

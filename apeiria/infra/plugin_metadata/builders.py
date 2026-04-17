"""Builders for plugin contract objects projected from native NoneBot plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.plugins.models import HandlerDescriptor, PluginDescriptor
from apeiria.shared.plugin_introspection import get_plugin_name
from apeiria.shared.plugin_metadata import PluginExtraData

if TYPE_CHECKING:
    from nonebot.matcher import Matcher
    from nonebot.plugin import Plugin


class PluginDescriptorBuilder:
    """Build formal plugin descriptors from loaded native plugins."""

    def build(self, plugin: "Plugin") -> PluginDescriptor:
        meta = plugin.metadata
        extra = self._get_plugin_extra(plugin)
        return PluginDescriptor(
            module_name=plugin.module_name,
            name=(
                extra.ui.label
                if extra is not None and extra.ui.label
                else get_plugin_name(plugin)
            ),
            description=meta.description if meta else None,
            homepage=meta.homepage if meta else None,
            source=self._resolve_plugin_source(plugin),
            plugin_type=extra.plugin_type.value if extra else "normal",
            admin_level=extra.admin_level if extra else 0,
            author=extra.author if extra else None,
            version=extra.version if extra else None,
            is_ui_hidden=extra.ui.hidden if extra is not None else False,
        )

    def _get_plugin_extra(self, plugin: "Plugin") -> PluginExtraData | None:
        meta = plugin.metadata
        if meta is None or not meta.extra:
            return None
        return PluginExtraData.from_extra(meta.extra)

    def _resolve_plugin_source(self, plugin: "Plugin") -> str:
        from apeiria.shared.plugin_introspection import get_plugin_source

        return get_plugin_source(plugin)


class HandlerDescriptorBuilder:
    """Build minimal handler descriptors from plugin matcher registrations."""

    def build_for_plugin(self, plugin: "Plugin") -> list[HandlerDescriptor]:
        return [
            self._build_handler_descriptor(plugin, matcher, ordinal)
            for ordinal, matcher in enumerate(
                sorted(
                    plugin.matcher,
                    key=self._matcher_sort_key,
                ),
                start=1,
            )
        ]

    def _build_handler_descriptor(
        self,
        plugin: "Plugin",
        matcher: type["Matcher"],
        ordinal: int,
    ) -> HandlerDescriptor:
        matcher_type = str(getattr(matcher, "type", "") or "event")
        priority = int(getattr(matcher, "priority", 1) or 1)
        propagation_mode = (
            "consume" if bool(getattr(matcher, "block", False)) else "handle"
        )
        matcher_module = str(getattr(matcher, "module_name", "") or plugin.module_name)
        matcher_name = getattr(matcher, "__name__", matcher_type or "matcher")
        source = getattr(matcher, "_source", None)
        source_lineno = getattr(source, "lineno", None)
        handler_id = ":".join(
            [
                plugin.module_name,
                matcher_module,
                str(priority),
                matcher_type,
                str(source_lineno or "na"),
                str(ordinal),
                str(matcher_name),
            ]
        )
        return HandlerDescriptor(
            handler_id=handler_id,
            plugin_module=plugin.module_name,
            phase=self._resolve_phase_name(matcher_type),
            subject_kind=matcher_type,
            priority=priority,
            propagation_mode=propagation_mode,
            matcher_type=matcher_type,
            is_temporary=bool(getattr(matcher, "temp", False)),
        )

    def _resolve_phase_name(self, matcher_type: str) -> str:
        normalized = matcher_type.strip() or "event"
        if normalized == "message":
            return "message_handlers"
        return f"native_{normalized}_handlers"

    def _matcher_sort_key(self, matcher: type["Matcher"]) -> tuple[object, ...]:
        return (
            int(getattr(matcher, "priority", 1) or 1),
            str(getattr(matcher, "module_name", "") or ""),
            str(getattr(matcher, "type", "") or ""),
            getattr(matcher, "__name__", ""),
        )


plugin_descriptor_builder = PluginDescriptorBuilder()
handler_descriptor_builder = HandlerDescriptorBuilder()

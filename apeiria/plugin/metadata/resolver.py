from __future__ import annotations

import nonebot
from nonebot.log import logger
from pydantic import BaseModel

from apeiria.config.reflector import reflect_model
from apeiria.config.schema import ConfigContract, FieldNode, PrimitiveField
from apeiria.plugin.metadata.api import PluginExtraData
from apeiria.plugin.metadata.registry import get_registered_plugin_config


def _apply_hint_to_field(field: FieldNode, hint: dict) -> None:
    if hint.get("label"):
        field.label = hint["label"]
    if hint.get("help"):
        field.description = hint["help"]
    if hint.get("order") is not None:
        field.order = int(hint["order"])
    if isinstance(field, PrimitiveField):
        if "secret" in hint:
            field.secret = bool(hint["secret"])
        if hint.get("choices"):
            field.choices = hint["choices"]


def merge_extra_hints(fields: list[FieldNode], extra_hints: list[dict]) -> None:
    hint_map: dict[str, dict] = {
        h.get("key", ""): h for h in extra_hints if h.get("key")
    }
    for field in fields:
        hint = hint_map.get(field.key)
        if hint is not None:
            _apply_hint_to_field(field, hint)


def _find_loaded_plugin(identifier: str):
    return next(
        (
            item
            for item in nonebot.get_loaded_plugins()
            if identifier in {item.module_name, item.name}
        ),
        None,
    )


def _module_candidate_for(name: str) -> str | None:
    from apeiria.plugin.scanner import manifest_module_candidate, scan_plugins

    for manifest in scan_plugins():
        if manifest.name == name:
            return manifest_module_candidate(manifest)
    return None


def resolve_config_namespace_contract(
    module_name: str,
) -> ConfigContract:
    registered = get_registered_plugin_config(module_name)
    plugin = _find_loaded_plugin(module_name)

    if registered is None and plugin is None:
        candidate = _module_candidate_for(module_name)
        if candidate and candidate != module_name:
            registered = get_registered_plugin_config(candidate)
            plugin = _find_loaded_plugin(candidate)

    if registered is not None:
        children: list[FieldNode] = [
            PrimitiveField(
                key=c.key,
                label=c.label or c.key,
                description=c.help or "",
                type="str",
                default=c.default,
                required=True,
                secret=c.secret,
                choices=c.choices or None,
                order=c.order,
            )
            for c in registered.configs
        ]
        return ConfigContract(
            namespace=registered.section,
            is_scoped=False,
            owner_kind="plugin",
            owner_id=registered.plugin_name,
            source="extra_only",
            fields=children,
            json_schema={},
        )

    if plugin is not None and plugin.metadata is not None:
        config_model = getattr(plugin.metadata, "config", None)
        has_pydantic_config = isinstance(config_model, type) and issubclass(
            config_model, BaseModel
        )

        extra_data = None
        if plugin.metadata.extra:
            extra_data = PluginExtraData.from_extra(plugin.metadata.extra)

        if has_pydantic_config:
            fields = reflect_model(config_model)
            if extra_data and extra_data.configs:
                merge_extra_hints(fields, extra_data.configs)

            is_scoped = any(f.kind in ("object", "array", "map") for f in fields)
            namespace = plugin.name if is_scoped else None

            try:
                json_schema = config_model.model_json_schema()
            except (TypeError, ValueError):
                json_schema = {}
                logger.debug("Failed to generate JSON schema for {}", module_name)

            return ConfigContract(
                namespace=namespace,
                is_scoped=is_scoped,
                owner_kind="plugin",
                owner_id=module_name,
                source="pydantic",
                fields=fields,
                json_schema=json_schema,
            )

        if extra_data and extra_data.configs:
            children: list[FieldNode] = [
                PrimitiveField(
                    key=c.get("key", ""),
                    label=c.get("label", c.get("key", "")),
                    description=c.get("help", ""),
                    type=str(c.get("type", "str")),
                    default=c.get("default"),
                    required=True,
                    secret=bool(c.get("secret", False)),
                    choices=c.get("choices"),
                    order=int(c.get("order", 99)),
                )
                for c in extra_data.configs
            ]
            return ConfigContract(
                namespace=None,
                is_scoped=False,
                owner_kind="plugin",
                owner_id=module_name,
                source="extra_only",
                fields=children,
                json_schema={},
            )

    return ConfigContract(
        namespace=None,
        is_scoped=False,
        owner_kind="plugin",
        owner_id=module_name,
        source="none",
        fields=[],
        json_schema={},
    )

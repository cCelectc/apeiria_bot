from __future__ import annotations

import nonebot
from nonebot.log import logger
from pydantic import BaseModel

from apeiria.config.reflector import reflect_model
from apeiria.config.schema import ConfigContract


def _find_loaded_plugin(identifier: str):
    return next(
        (
            item
            for item in nonebot.get_loaded_plugins()
            if identifier in {item.module_name, item.name}
        ),
        None,
    )


def resolve_config_namespace_contract(module_name: str) -> ConfigContract:
    plugin = _find_loaded_plugin(module_name)

    if plugin is not None and plugin.metadata is not None:
        config_model = getattr(plugin.metadata, "config", None)

        if isinstance(config_model, type) and issubclass(config_model, BaseModel):
            fields = reflect_model(config_model)
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

    return ConfigContract(
        namespace=None,
        is_scoped=False,
        owner_kind="plugin",
        owner_id=module_name,
        source="none",
        fields=[],
        json_schema={},
    )

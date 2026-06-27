from __future__ import annotations

import importlib

import nonebot
from nonebot.log import logger
from pydantic import BaseModel

from apeiria.config.reflector import reflect_model
from apeiria.config.schema import ConfigContract


def _find_config_in_module(module_name: str) -> type[BaseModel] | None:
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        logger.debug("Failed to import adapter module: {}", module_name)
        return None

    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, BaseModel)
            and attr is not BaseModel
            and attr_name.lower() in ("config", "adapterconfig", "settings")
        ):
            return attr
    return None


def resolve_adapter_config(adapter_name: str) -> ConfigContract | None:
    try:
        adapter = nonebot.get_adapter(adapter_name)
    except (ValueError, KeyError):
        logger.debug("Adapter not found: {}", adapter_name)
        return None

    adapter_cls = adapter.__class__
    config_cls = _find_config_in_module(adapter_cls.__module__)

    if config_cls is None:
        return None

    fields = reflect_model(config_cls)
    is_scoped = any(f.kind in ("object", "array", "map") for f in fields)
    namespace = adapter_name if is_scoped else None

    try:
        json_schema = config_cls.model_json_schema()
    except (TypeError, ValueError):
        json_schema = {}

    return ConfigContract(
        namespace=namespace,
        is_scoped=is_scoped,
        owner_kind="adapter",
        owner_id=adapter_name,
        source="pydantic",
        fields=fields,
        json_schema=json_schema,
    )

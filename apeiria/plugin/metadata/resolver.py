from dataclasses import dataclass

import nonebot
from pydantic import BaseModel

from apeiria.plugin.metadata.api import PluginExtraData, RegisterConfig
from apeiria.plugin.metadata.registry import get_registered_plugin_config


@dataclass
class ConfigNamespaceContract:
    namespace: str
    owner_kind: str
    owner_id: str
    source: str
    has_config_model: bool
    configs: list[RegisterConfig]


def resolve_config_namespace_contract(
    module_name: str,
) -> ConfigNamespaceContract:
    registered = get_registered_plugin_config(module_name)
    if registered is not None:
        return ConfigNamespaceContract(
            namespace=registered.section,
            owner_kind="plugin",
            owner_id=registered.plugin_name,
            source=registered.source,
            has_config_model=bool(registered.configs),
            configs=registered.configs,
        )

    plugin = next(
        (
            item
            for item in nonebot.get_loaded_plugins()
            if item.module_name == module_name
        ),
        None,
    )
    if plugin is not None and plugin.metadata is not None:
        configs: list[RegisterConfig] = []
        has_model = False

        config_model = getattr(plugin.metadata, "config", None)
        if isinstance(config_model, type) and issubclass(config_model, BaseModel):
            has_model = True
            configs = _model_to_configs(config_model)

        extra_data = None
        if plugin.metadata.extra:
            extra_data = PluginExtraData.from_extra(plugin.metadata.extra)

        has_extra_configs = extra_data is not None and bool(extra_data.configs)
        section = module_name.rsplit(".", maxsplit=1)[-1]
        return ConfigNamespaceContract(
            namespace=section,
            owner_kind="plugin",
            owner_id=module_name,
            source="plugin_metadata",
            has_config_model=has_model or has_extra_configs,
            configs=configs,
        )

    section = module_name.rsplit(".", maxsplit=1)[-1]
    return ConfigNamespaceContract(
        namespace=section,
        owner_kind="plugin",
        owner_id=module_name,
        source="none",
        has_config_model=False,
        configs=[],
    )


def _model_to_configs(model: type[BaseModel]) -> list[RegisterConfig]:
    result: list[RegisterConfig] = []
    for field_name, field_info in model.model_fields.items():
        default = field_info.get_default(call_default_factory=True)
        result.append(
            RegisterConfig(
                key=field_name,
                default=default,
                help=field_info.description or "",
                type=field_info.annotation or str,
            )
        )
    return result

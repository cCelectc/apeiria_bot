from dataclasses import dataclass

from apeiria.plugin.metadata.api import RegisterConfig


@dataclass
class PluginConfigRegistration:
    plugin_name: str
    section: str
    configs: list[RegisterConfig]
    source: str = "manual"


_REGISTRY: dict[str, PluginConfigRegistration] = {}


def _name_candidates(name: str) -> tuple[str, ...]:
    candidates = [name]
    underscored = name.replace("-", "_")
    if underscored not in candidates:
        candidates.append(underscored)
    dashed = name.replace("_", "-")
    if dashed not in candidates:
        candidates.append(dashed)
    return tuple(candidates)


def register_plugin_config(
    plugin_name: str,
    *,
    section: str | None = None,
    configs: list[RegisterConfig] | None = None,
) -> PluginConfigRegistration:
    resolved_section = section or plugin_name.rsplit(".", maxsplit=1)[-1]
    registration = PluginConfigRegistration(
        plugin_name=plugin_name,
        section=resolved_section,
        configs=list(configs or []),
    )
    for candidate in _name_candidates(plugin_name):
        _REGISTRY[candidate] = registration
    return registration


def get_registered_plugin_config(
    plugin_name: str,
) -> PluginConfigRegistration | None:
    for candidate in _name_candidates(plugin_name):
        if candidate in _REGISTRY:
            return _REGISTRY[candidate]
    return None


def iter_registered_plugin_configs() -> list[PluginConfigRegistration]:
    seen: set[str] = set()
    result: list[PluginConfigRegistration] = []
    for reg in _REGISTRY.values():
        if reg.plugin_name not in seen:
            seen.add(reg.plugin_name)
            result.append(reg)
    return result

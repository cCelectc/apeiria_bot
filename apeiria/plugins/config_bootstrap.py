from apeiria.plugins.metadata.registry import PluginConfigConflictError
from apeiria.plugins.metadata.resolver import (
    PluginScanCandidate,
    collect_plugin_config_candidates,
    ensure_config_namespace_contract,
)


def _register_candidate(candidate: PluginScanCandidate) -> None:
    try:
        ensure_config_namespace_contract(candidate)
    except PluginConfigConflictError as exc:
        msg = f"failed to bootstrap plugin config for {candidate.module_name}: {exc}"
        raise RuntimeError(msg) from exc


def bootstrap_plugin_configs() -> None:
    for candidate in collect_plugin_config_candidates():
        _register_candidate(candidate)

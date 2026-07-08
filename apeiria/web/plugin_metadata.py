from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apeiria.plugin.scanner import (
    manifest_module_candidate,
    read_installed_version,
)

if TYPE_CHECKING:
    from apeiria.plugin.scanner import PluginManifest


def _lookup(
    manifest: PluginManifest, metadata_map: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    if manifest.name in metadata_map:
        return metadata_map[manifest.name]
    return metadata_map.get(manifest_module_candidate(manifest))


def merge_plugin_metadata(
    manifests: list[PluginManifest],
    metadata_map: dict[str, dict[str, Any]],
    dep_graph: dict | None = None,
    dep_reverse: dict | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for manifest in manifests:
        meta = _lookup(manifest, metadata_map) or {}
        name = manifest.name
        module = manifest_module_candidate(manifest)
        rows.append(
            {
                "name": name,
                "source": manifest.source,
                "enabled": manifest.enabled,
                "path_or_module": manifest.path_or_module,
                "module": module,
                "display_name": meta.get("name"),
                "description": meta.get("description"),
                "usage": meta.get("usage"),
                "type": meta.get("type"),
                "homepage": meta.get("homepage"),
                "supported_adapters": meta.get("supported_adapters"),
                "can_disable": True,
                "can_uninstall": manifest.source in ("local", "pypi"),
                "installed_version": read_installed_version(manifest.path_or_module)
                if manifest.source == "pypi"
                else None,
                "depends_on": sorted(dep_graph.get(name, set())) if dep_graph else [],
                "depended_by": sorted(dep_reverse.get(name, set()))
                if dep_reverse
                else [],
            }
        )
    return rows

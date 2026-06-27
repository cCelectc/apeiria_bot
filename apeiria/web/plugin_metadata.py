from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apeiria.plugin.scanner import manifest_module_candidate

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
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for manifest in manifests:
        meta = _lookup(manifest, metadata_map) or {}
        rows.append(
            {
                "name": manifest.name,
                "source": manifest.source,
                "enabled": manifest.enabled,
                "path_or_module": manifest.path_or_module,
                "module": manifest_module_candidate(manifest),
                "display_name": meta.get("name"),
                "description": meta.get("description"),
                "usage": meta.get("usage"),
                "type": meta.get("type"),
                "homepage": meta.get("homepage"),
                "supported_adapters": meta.get("supported_adapters"),
            }
        )
    return rows

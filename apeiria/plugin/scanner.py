from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_REQUIREMENT_NAME = re.compile(r"^[A-Za-z0-9._-]+")

BUILTIN_LIST = [
    "admin",
    "help",
    "repeater",
    "trigger_reply",
    "friendship",
    "contact_owner",
    "self_revoke",
]


@dataclass
class PluginManifest:
    name: str
    path_or_module: str
    enabled: bool
    source: str  # "builtin" | "local" | "pypi" | "dependency"


def requirement_to_module(requirement: str) -> str:
    match = _REQUIREMENT_NAME.match(requirement.strip())
    base = match.group(0) if match else requirement
    base = base.split("[", 1)[0]
    return base.replace("-", "_")


def manifest_module_candidate(manifest: PluginManifest) -> str:
    if manifest.source == "pypi":
        return requirement_to_module(manifest.path_or_module)
    if manifest.source == "local":
        return Path(manifest.path_or_module).name
    return manifest.path_or_module.rsplit(".", 1)[-1]


def _load_plugins_yaml() -> dict:
    yaml_path = Path(".apeiria/plugins.yaml")
    if not yaml_path.exists():
        return {"dirs": [], "packages": {}, "states": {}}
    return yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}


def _is_enabled(name: str, data: dict) -> bool:
    states = data.get("states") or {}
    if name in states:
        return bool(states[name].get("enabled", True))
    return True


def scan_plugins() -> list[PluginManifest]:
    data = _load_plugins_yaml()
    dirs = data.get("dirs") or []
    packages = data.get("packages") or {}

    result: list[PluginManifest] = [
        PluginManifest(
            name=name,
            path_or_module=f"apeiria.builtin_plugins.{name}",
            enabled=_is_enabled(name, data),
            source="builtin",
        )
        for name in BUILTIN_LIST
    ]

    for scan_dir in dirs:
        dir_path = Path(scan_dir)
        if not dir_path.is_dir():
            continue
        for entry in sorted(dir_path.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            init_file = entry / "__init__.py"
            if not init_file.is_file():
                continue
            name = entry.name
            result.append(
                PluginManifest(
                    name=name,
                    path_or_module=str(entry.resolve()),
                    enabled=_is_enabled(name, data),
                    source="local",
                )
            )

    for pkg_name, pkg_info in packages.items():
        module = pkg_info if isinstance(pkg_info, str) else pkg_info.get("module", "")
        result.append(
            PluginManifest(
                name=pkg_name,
                path_or_module=module,
                enabled=_is_enabled(pkg_name, data),
                source="pypi",
            )
        )

    return result

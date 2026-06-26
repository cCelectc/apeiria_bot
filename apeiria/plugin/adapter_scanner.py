from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class AdapterManifest:
    name: str
    module_name: str
    enabled: bool
    source: str  # "builtin" | "pypi"


def _load_adapters_yaml() -> dict:
    yaml_path = Path(".apeiria/adapters.yaml")
    if not yaml_path.exists():
        return {"packages": {}, "states": {}}
    return yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}


def _is_adapter_enabled(name: str, data: dict) -> bool:
    states = data.get("states") or {}
    if name in states:
        return bool(states[name].get("enabled", True))
    return True


def _read_toml_adapters(toml_path: Path) -> list[dict]:
    if not toml_path.exists():
        return []
    raw = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    adapters_cfg = raw.get("tool", {}).get("nonebot", {}).get("adapters", {})
    if not isinstance(adapters_cfg, dict):
        return []
    entries: list[dict] = []
    for key, adapter_entries in adapters_cfg.items():
        if key == "@local":
            continue
        if not isinstance(adapter_entries, list):
            continue
        entries.extend(
            {"name": e.get("name", key), "module_name": e["module_name"]}
            for e in adapter_entries
            if isinstance(e, dict) and e.get("module_name")
        )
    return entries


def scan_adapters() -> list[AdapterManifest]:
    data = _load_adapters_yaml()

    result: list[AdapterManifest] = []

    for entry in _read_toml_adapters(Path("pyproject.toml")):
        name = entry["name"]
        result.append(
            AdapterManifest(
                name=name,
                module_name=entry["module_name"],
                enabled=_is_adapter_enabled(name, data),
                source="builtin",
            )
        )

    for entry in _read_toml_adapters(Path(".apeiria/pyproject.toml")):
        name = entry["name"]
        result.append(
            AdapterManifest(
                name=name,
                module_name=entry["module_name"],
                enabled=_is_adapter_enabled(name, data),
                source="pypi",
            )
        )

    return result

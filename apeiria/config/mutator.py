from __future__ import annotations

from pathlib import Path
from typing import Any

import tomlkit

_PROJECT_ROOT = Path()


def add_plugin(plugin_name: str) -> None:
    _append_to_list("apeiria.plugins.toml", "plugins", plugin_name)


def remove_plugin(plugin_name: str) -> None:
    _remove_from_list("apeiria.plugins.toml", "plugins", plugin_name)


def add_adapter(adapter_entry: dict[str, Any]) -> None:
    _append_to_list("apeiria.adapters.toml", "adapters", adapter_entry)


def remove_adapter(adapter_name: str) -> None:
    path = _PROJECT_ROOT / "apeiria.adapters.toml"
    if not path.exists():
        return
    doc = _read_toml(path)
    adapters = doc.get("adapters", [])
    doc["adapters"] = [a for a in adapters if a.get("name") != adapter_name]
    _write_toml(path, doc)


def _append_to_list(filename: str, key: str, value: Any) -> None:
    path = _PROJECT_ROOT / filename
    doc = _read_toml(path) if path.exists() else tomlkit.document()
    items = doc.get(key, [])
    if value not in items:
        items.append(value)
    doc[key] = items
    _write_toml(path, doc)


def _remove_from_list(filename: str, key: str, value: Any) -> None:
    path = _PROJECT_ROOT / filename
    if not path.exists():
        return
    doc = _read_toml(path)
    items = doc.get(key, [])
    if value in items:
        items.remove(value)
    doc[key] = items
    _write_toml(path, doc)


def _read_toml(path: Path) -> tomlkit.TOMLDocument:
    with path.open(encoding="utf-8") as f:
        return tomlkit.load(f)


def _write_toml(path: Path, doc: tomlkit.TOMLDocument) -> None:
    with path.open("w", encoding="utf-8") as f:
        tomlkit.dump(doc, f)

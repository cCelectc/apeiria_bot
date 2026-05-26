"""Module discovery cache helpers used by runtime/plugin management."""

from __future__ import annotations

from functools import lru_cache
from importlib.machinery import PathFinder
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.machinery import ModuleSpec


def invalidate_module_discovery_caches() -> None:
    resolve_module_spec.cache_clear()
    is_module_importable.cache_clear()


@lru_cache(maxsize=512)
def resolve_module_spec(module_name: str | None) -> ModuleSpec | None:
    """Resolve module spec with fallback to builtin nonebot plugins."""
    if not module_name:
        return None

    spec = _find_module_spec_without_import(module_name)

    if (spec is None or spec.origin is None) and "." not in module_name:
        spec = _find_module_spec_without_import(f"nonebot.plugins.{module_name}")
    return spec


@lru_cache(maxsize=512)
def is_module_importable(module_name: str | None) -> bool:
    """Return whether a module can be imported via standard discovery."""
    spec = resolve_module_spec(module_name)
    return spec is not None


def _find_module_spec_without_import(module_name: str) -> ModuleSpec | None:
    try:
        if "." not in module_name:
            return PathFinder.find_spec(module_name)

        package_name, child_name = module_name.rsplit(".", 1)
        package_spec = _find_module_spec_without_import(package_name)
        if package_spec is None:
            return None
        search_locations = package_spec.submodule_search_locations
        if search_locations is None:
            return None
        return PathFinder.find_spec(child_name, search_locations)
    except (ImportError, ModuleNotFoundError, ValueError):
        return None

"""Module discovery cache helpers used by runtime/plugin management."""

from __future__ import annotations

from functools import lru_cache
from importlib.util import find_spec
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

    try:
        spec = find_spec(module_name)
    except (ImportError, ModuleNotFoundError, ValueError):
        spec = None

    if (spec is None or spec.origin is None) and "." not in module_name:
        try:
            spec = find_spec(f"nonebot.plugins.{module_name}")
        except (ImportError, ModuleNotFoundError, ValueError):
            spec = None
    return spec


@lru_cache(maxsize=512)
def is_module_importable(module_name: str | None) -> bool:
    """Return whether a module can be imported via standard discovery."""
    spec = resolve_module_spec(module_name)
    return spec is not None

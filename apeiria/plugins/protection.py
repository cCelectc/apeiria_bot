from __future__ import annotations

from functools import lru_cache

from apeiria._framework_loader import (
    get_framework_dependency_plugin_modules,
)

ALWAYS_PROTECTED_PLUGIN_MODULES = frozenset({"apeiria.builtin_plugins.web_ui"})


@lru_cache(maxsize=1)
def framework_dependency_plugin_modules() -> frozenset[str]:
    return get_framework_dependency_plugin_modules()


@lru_cache(maxsize=1)
def core_plugin_modules() -> frozenset[str]:
    return framework_dependency_plugin_modules() | ALWAYS_PROTECTED_PLUGIN_MODULES


def is_framework_dependency_plugin_module(module_name: str) -> bool:
    return module_name in framework_dependency_plugin_modules()


def get_plugin_kind(module_name: str) -> str:
    return "core" if module_name in core_plugin_modules() else "plugin"


def get_default_protection_mode(module_name: str) -> str:
    return "required" if module_name in core_plugin_modules() else "normal"


def is_protected_plugin_module(module_name: str) -> bool:
    return get_default_protection_mode(module_name) == "required"

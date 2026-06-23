"""Plugin metadata and dependency inspection helpers."""

from __future__ import annotations

import ast
from functools import lru_cache
from importlib.metadata import packages_distributions
from pathlib import Path
from typing import TYPE_CHECKING

import nonebot

from apeiria.config.plugins import plugin_config_service
from apeiria.environment.extension_project import (
    pending_plugin_module_uninstalls,
    pending_plugin_requirement_removals,
)
from apeiria.i18n import t
from apeiria.plugins.metadata.api import PluginExtraData
from apeiria.plugins.metadata.module_cache import (
    invalidate_module_discovery_caches,
    resolve_module_spec,
)
from apeiria.plugins.package_ids import normalize_package_id
from apeiria.plugins.protection import (
    is_framework_dependency_plugin_module,
    is_protected_plugin_module,
)
from apeiria.plugins.state import get_disabled_plugin_modules_sync
from apeiria.utils.project_context import current_project_root, package_root

if TYPE_CHECKING:
    from collections.abc import Mapping

    from nonebot.plugin import Plugin


_USER_MANAGED_SOURCES = {"custom", "external"}


def _official_plugin_root() -> Path:
    return (package_root() / "apeiria" / "builtin_plugins").resolve()


def _custom_plugin_root() -> Path:
    return (current_project_root() / "local_plugins").resolve()


def get_plugin_extra(plugin: Plugin) -> PluginExtraData | None:
    """Extract PluginExtraData from a loaded plugin."""
    if plugin.metadata and plugin.metadata.extra:
        return PluginExtraData.from_extra(plugin.metadata.extra)
    return None


def get_plugin_name(plugin: Plugin) -> str:
    """Get display name of a plugin."""
    if plugin.metadata and plugin.metadata.name:
        return plugin.metadata.name
    return plugin.name


def get_plugin_required_plugins(plugin: Plugin) -> list[str]:
    """Get declared plugin dependencies from metadata or source `require()` calls."""
    extra = get_plugin_extra(plugin)
    if extra:
        return [
            module
            for module in extra.required_plugins
            if isinstance(module, str) and module
        ]

    module = getattr(plugin, "module", None)
    module_file = getattr(module, "__file__", None)
    if not isinstance(module_file, str) or not module_file:
        return []

    return _scan_required_plugins_from_source(_plugin_source_paths(Path(module_file)))


def get_module_required_plugins(module_name: str) -> list[str]:
    """Get declared dependencies for an importable module name."""
    source_paths = _module_source_paths(module_name)
    if not source_paths:
        return []
    return _scan_required_plugins_from_source(source_paths)


def prewarm_plugin_module_caches(module_names: set[str]) -> None:
    """Warm module resolution and dependency caches for plugin management."""
    pending = [module_name for module_name in module_names if module_name]
    seen: set[str] = set()

    while pending:
        module_name = pending.pop()
        if not module_name or module_name in seen:
            continue
        seen.add(module_name)

        spec = resolve_module_spec(module_name)
        if spec is None:
            continue

        get_plugin_source_by_module_name(module_name)
        dependencies = get_module_required_plugins(module_name)
        pending.extend(
            dependency
            for dependency in dependencies
            if dependency and dependency not in seen
        )


def invalidate_plugin_management_caches() -> None:
    """Clear module discovery caches used by plugin management views."""
    invalidate_module_discovery_caches()
    _scan_required_plugins_from_source.cache_clear()


def find_loaded_plugin(name: str) -> Plugin | None:
    """Find loaded plugin by module name or display name."""
    for plugin in nonebot.get_loaded_plugins():
        if plugin.module_name == name or get_plugin_name(plugin) == name:
            return plugin
    return None


def get_pending_uninstall_plugin_modules() -> set[str]:
    """Return loaded plugins explicitly scheduled for deferred removal."""
    pending_modules = set(pending_plugin_module_uninstalls())
    pending_requirements = {
        normalize_package_id(item) or item
        for item in pending_plugin_requirement_removals()
    }
    if not pending_requirements:
        return pending_modules

    top_level_packages = packages_distributions()
    package_bindings = plugin_config_service.read_project_plugin_config()["packages"]
    for plugin in nonebot.get_loaded_plugins():
        if get_plugin_source(plugin) not in _USER_MANAGED_SOURCES:
            continue
        package_name = _get_plugin_distribution_name(
            plugin,
            top_level_packages,
            package_bindings,
        )
        normalized = normalize_package_id(package_name) if package_name else None
        if normalized and normalized in pending_requirements:
            pending_modules.add(plugin.module_name)
    return pending_modules


def is_plugin_pending_uninstall(module_name: str) -> bool:
    """Return whether the plugin is loaded now but already scheduled for removal."""
    return module_name in get_pending_uninstall_plugin_modules()


def get_plugin_dependents(
    module_name: str,
    *,
    include_pending: bool = False,
) -> list[str]:
    """Get loaded plugins that depend on the target plugin."""
    pending_modules = (
        set() if include_pending else get_pending_uninstall_plugin_modules()
    )
    disabled_modules = get_disabled_plugin_modules_sync()
    dependents = {
        get_plugin_name(plugin)
        for plugin in nonebot.get_loaded_plugins()
        if plugin.module_name not in pending_modules
        if plugin.module_name not in disabled_modules
        if module_name in get_plugin_required_plugins(plugin)
    }
    return sorted(dependents)


def get_plugin_source(plugin: Plugin) -> str:
    """Classify plugin source for management UI."""
    module = getattr(plugin, "module", None)
    module_file = getattr(module, "__file__", None)
    if module_file:
        try:
            resolved = Path(module_file).resolve()
        except OSError:
            resolved = None
        if resolved:
            if _official_plugin_root() in resolved.parents:
                return "builtin"
            if _custom_plugin_root() in resolved.parents:
                return "custom"

    if is_framework_dependency_plugin_module(plugin.module_name):
        return "framework"
    return "external"


def get_plugin_source_by_module_name(module_name: str) -> str:
    """Classify plugin source using module name when no loaded plugin exists."""
    spec = resolve_module_spec(module_name)
    origin = getattr(spec, "origin", None)
    if isinstance(origin, str) and origin:
        try:
            resolved = Path(origin).resolve()
        except OSError:
            resolved = None
        if resolved:
            if _official_plugin_root() in resolved.parents:
                return "builtin"
            if _custom_plugin_root() in resolved.parents:
                return "custom"

    if is_framework_dependency_plugin_module(module_name):
        return "framework"
    return "external"


def get_plugin_protection_reason(module_name: str) -> str | None:
    """Return human-readable reason when a plugin should not be disabled."""
    reasons: list[str] = []
    if is_framework_dependency_plugin_module(module_name):
        reasons.append(t("common.framework_required"))

    dependents = get_plugin_dependents(module_name)
    if dependents:
        reasons.append(t("common.required_by_plugins", plugins=", ".join(dependents)))

    return "；".join(reasons) if reasons else None


def is_plugin_protected(module_name: str) -> bool:
    """Check whether a plugin is protected from being disabled."""
    return is_protected_plugin_module(module_name) or (
        get_plugin_protection_reason(module_name) is not None
    )


def _plugin_source_paths(origin: Path) -> tuple[str, ...]:
    try:
        resolved = origin.resolve()
    except OSError:
        return ()

    if resolved.name == "__init__.py":
        try:
            return tuple(
                str(path)
                for path in sorted(resolved.parent.rglob("*.py"))
                if path.is_file()
            )
        except OSError:
            return ()
    return (str(resolved),)


def _module_source_paths(module_name: str) -> tuple[str, ...]:
    spec = resolve_module_spec(module_name)
    if spec is None or spec.origin is None:
        return ()
    return _plugin_source_paths(Path(spec.origin))


@lru_cache(maxsize=256)
def _scan_required_plugins_from_source(source_paths: tuple[str, ...]) -> list[str]:
    required: list[str] = []
    seen: set[str] = set()

    for raw_path in source_paths:
        path = Path(raw_path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        for dependency in _iter_required_plugins_in_tree(tree):
            if not dependency or dependency in seen:
                continue
            seen.add(dependency)
            required.append(dependency)

    return required


def _require_aliases(tree: ast.AST) -> set[str]:
    aliases = {"require"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module != "nonebot":
            continue
        for alias in node.names:
            if alias.name == "require":
                aliases.add(alias.asname or alias.name)
    return aliases


def _iter_required_plugins_in_tree(tree: ast.AST) -> list[str]:
    aliases = _require_aliases(tree)
    dependencies: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id not in aliases:
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if not isinstance(first_arg, ast.Constant) or not isinstance(
            first_arg.value,
            str,
        ):
            continue
        dependencies.append(first_arg.value.strip())
    return dependencies


def _get_plugin_distribution_name(
    plugin: Plugin,
    top_level_packages: Mapping[str, list[str]],
    package_bindings: dict[str, list[str]] | None = None,
) -> str | None:
    package_bindings = (
        package_bindings
        if package_bindings is not None
        else plugin_config_service.read_project_plugin_config()["packages"]
    )
    for package_name, module_names in package_bindings.items():
        if plugin.module_name in module_names:
            return package_name
    top_level = plugin.module_name.split(".", 1)[0]
    inferred = top_level_packages.get(top_level, [])
    return inferred[0] if inferred else None

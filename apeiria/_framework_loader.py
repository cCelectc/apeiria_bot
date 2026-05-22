from __future__ import annotations

import ast
from functools import lru_cache
from importlib.util import find_spec
from pathlib import Path

import nonebot

FRAMEWORK_PLUGIN_MODULES = (
    "nonebot_plugin_apscheduler",
    "nonebot_plugin_localstore",
    "nonebot_plugin_alconna",
)

BUILTIN_APPLICATION_PLUGIN_MODULES = (
    "apeiria.builtin_plugins.ai",
    "apeiria.builtin_plugins.render",
    "apeiria.builtin_plugins.admin",
    "apeiria.builtin_plugins.help",
    "apeiria.builtin_plugins.self_revoke",
    "apeiria.builtin_plugins.web_ui",
)

FRAMEWORK_BUILTIN_PLUGIN_NAMES = ("echo",)


def iter_builtin_plugin_modules() -> tuple[str, ...]:
    """Return Apeiria built-in application plugin modules."""
    return tuple(sorted(BUILTIN_APPLICATION_PLUGIN_MODULES))


def get_framework_dependency_plugin_modules() -> frozenset[str]:
    """Return non-builtin plugin modules required by the framework runtime."""
    discovered: set[str] = set()
    pending: list[str] = list(FRAMEWORK_PLUGIN_MODULES)
    builtin_modules = set(iter_builtin_plugin_modules())

    while pending:
        module_name = pending.pop()
        if module_name in discovered:
            continue
        discovered.add(module_name)
        pending.extend(
            dependency
            for dependency in _get_module_required_plugins(module_name)
            if dependency not in discovered
        )

    return frozenset(
        module_name for module_name in discovered if module_name not in builtin_modules
    )


def _get_module_required_plugins(module_name: str) -> tuple[str, ...]:
    source_paths = _module_source_paths(module_name)
    if not source_paths:
        return ()
    return _scan_required_plugins_from_source(source_paths)


def _module_source_paths(module_name: str) -> tuple[str, ...]:
    try:
        spec = find_spec(module_name)
    except (ImportError, ModuleNotFoundError, ValueError):
        spec = None

    if spec is None or spec.origin is None:
        return ()
    return _plugin_source_paths(Path(spec.origin))


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


@lru_cache(maxsize=256)
def _scan_required_plugins_from_source(
    source_paths: tuple[str, ...],
) -> tuple[str, ...]:
    required: list[str] = []
    seen: set[str] = set()

    for raw_path in source_paths:
        path = Path(raw_path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        aliases = _require_aliases(tree)
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
            dependency = first_arg.value.strip()
            if not dependency or dependency in seen:
                continue
            seen.add(dependency)
            required.append(dependency)

    return tuple(required)


def _require_aliases(tree: ast.AST) -> set[str]:
    aliases = {"require"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module != "nonebot":
            continue
        for alias in node.names:
            if alias.name == "require":
                aliases.add(alias.asname or alias.name)
    return aliases


def load_framework() -> None:
    """Load framework plugins, builtins, and core side effects."""
    from nonebot.log import logger

    from apeiria.db.schema import ensure_database_ready_sync
    from apeiria.log import setup_logging
    from apeiria.plugins.state import (
        get_disabled_plugin_modules_sync,
    )

    setup_logging()

    nonebot.load_builtin_plugins(*FRAMEWORK_BUILTIN_PLUGIN_NAMES)
    for plugin in FRAMEWORK_PLUGIN_MODULES:
        nonebot.load_plugin(plugin)

    ensure_database_ready_sync()

    disabled_builtin_modules = get_disabled_plugin_modules_sync(
        BUILTIN_APPLICATION_PLUGIN_MODULES
    )
    for plugin in BUILTIN_APPLICATION_PLUGIN_MODULES:
        if plugin in disabled_builtin_modules:
            logger.info("Skip disabled builtin plugin {}", plugin)
            continue
        nonebot.load_plugin(plugin)

    from apeiria.bot.hooks.registry import register_bot_hooks

    register_bot_hooks()

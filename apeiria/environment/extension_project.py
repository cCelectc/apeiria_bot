from __future__ import annotations

"""Helpers for the managed extension runtime environment."""

import json
import logging
import os
import site
import subprocess
import sys
from importlib import import_module
from pathlib import Path
from shutil import which
from typing import Final

from apeiria.plugins.package_ids import normalize_package_id
from apeiria.utils.files import atomic_write_text
from apeiria.utils.project_context import current_project_root

_PLUGIN_PROJECT_RELATIVE_PATH: Final = Path(".apeiria") / "extensions"
_PLUGIN_PROJECT_NAME: Final = "apeiria-user-plugins"
_PYTHON_VERSION_FALLBACK: Final = ">=3.10, <4.0"
_PENDING_PLUGIN_UNINSTALLS_FILE: Final = "pending_plugin_uninstalls.json"
_PENDING_PLUGIN_MODULE_UNINSTALLS_FILE: Final = "pending_plugin_module_uninstalls.json"
_logger = logging.getLogger("apeiria.environment.extension_project")


def _project_root() -> Path:
    return current_project_root()


def _load_toml_module():
    try:
        return import_module("tomllib")
    except ModuleNotFoundError:
        pass
    try:
        return import_module("tomli")
    except ModuleNotFoundError:
        pass
    return None


def plugin_project_root() -> Path:
    """Return the root directory of the managed extension project."""
    return _project_root() / _PLUGIN_PROJECT_RELATIVE_PATH


def plugin_project_exists() -> bool:
    return plugin_project_pyproject_path().is_file()


def plugin_project_pyproject_path() -> Path:
    return plugin_project_root() / "pyproject.toml"


def plugin_project_lock_path() -> Path:
    return plugin_project_root() / "uv.lock"


def plugin_pending_uninstalls_path() -> Path:
    return plugin_project_root() / _PENDING_PLUGIN_UNINSTALLS_FILE


def plugin_pending_module_uninstalls_path() -> Path:
    return plugin_project_root() / _PENDING_PLUGIN_MODULE_UNINSTALLS_FILE


def plugin_project_venv_path() -> Path:
    return plugin_project_root() / ".venv"


def uv_cache_dir() -> Path:
    return _project_root() / ".apeiria" / "cache" / "uv"


def _main_requires_python() -> str:
    pyproject_path = _project_root() / "pyproject.toml"
    toml_module = _load_toml_module()
    if toml_module is None:
        return _PYTHON_VERSION_FALLBACK
    try:
        with pyproject_path.open("rb") as file:
            data = toml_module.load(file)
    except (OSError, ValueError):
        return _PYTHON_VERSION_FALLBACK

    project = data.get("project")
    if not isinstance(project, dict):
        return _PYTHON_VERSION_FALLBACK
    requires_python = project.get("requires-python")
    if not isinstance(requires_python, str) or not requires_python.strip():
        return _PYTHON_VERSION_FALLBACK
    return requires_python.strip()


def _plugin_project_template() -> str:
    requires_python = _main_requires_python()
    return "\n".join(
        [
            "[project]",
            f'name = "{_PLUGIN_PROJECT_NAME}"',
            'version = "0.0.0"',
            f'requires-python = "{requires_python}"',
            "dependencies = []",
            "",
            "[tool.uv]",
            "package = false",
            "",
        ]
    )


def ensure_plugin_project() -> Path:
    """Create the extension project scaffold when it does not exist yet."""
    root = plugin_project_root()
    root.mkdir(parents=True, exist_ok=True)
    pyproject_path = plugin_project_pyproject_path()
    if not pyproject_path.exists():
        pyproject_path.write_text(_plugin_project_template(), encoding="utf-8")
    return root


def find_uv_executable() -> str:
    """Resolve the `uv` executable required for extension environment changes."""
    executable = which("uv")
    if executable is None:
        msg = "uv is required but was not found in PATH"
        raise RuntimeError(msg)
    return executable


def _run_uv(args: list[str], *, cwd: Path) -> None:
    executable = find_uv_executable()
    cache_dir = uv_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["UV_CACHE_DIR"] = str(cache_dir)
    env["UV_PROJECT_ENVIRONMENT"] = str(cwd / ".venv")
    env.pop("VIRTUAL_ENV", None)
    result = subprocess.run(
        [executable, *args],
        cwd=cwd,
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output_parts = [
            part.strip()
            for part in (result.stdout, result.stderr)
            if part and part.strip()
        ]
        output = "\n".join(output_parts)
        msg = f"uv command failed: {' '.join(args)}"
        if output:
            msg = f"{msg}\n{output}"
        raise RuntimeError(msg)


def sync_plugin_project(*, locked: bool = True) -> Path:
    """Sync the managed extension environment with its pyproject and lockfile."""
    root = ensure_plugin_project()
    args = ["sync"]
    if locked and plugin_project_lock_path().exists():
        args.append("--locked")
    _run_uv(args, cwd=root)
    return root


def add_plugin_requirement(requirement: str, extra_args: tuple[str, ...] = ()) -> None:
    root = ensure_plugin_project()
    _run_uv(["add", requirement, *extra_args], cwd=root)


def update_plugin_requirement(
    requirement: str,
    extra_args: tuple[str, ...] = (),
) -> None:
    root = ensure_plugin_project()
    target = normalize_package_id(requirement) or requirement
    _run_uv(["add", "--upgrade", target, *extra_args], cwd=root)


def remove_plugin_requirement(
    requirement: str,
    extra_args: tuple[str, ...] = (),
) -> None:
    root = ensure_plugin_project()
    target = normalize_package_id(requirement) or requirement
    _run_uv(["remove", target, *extra_args], cwd=root)


def enqueue_plugin_requirement_removal(requirement: str) -> bool:
    target = resolve_declared_plugin_requirement(requirement).strip()
    if not target:
        return False

    normalized_target = normalize_package_id(target) or target
    pending = _read_pending_plugin_uninstalls()
    normalized_pending = {normalize_package_id(item) or item for item in pending}
    if normalized_target in normalized_pending:
        return False

    pending.append(target)
    _write_pending_plugin_uninstalls(pending)
    return True


def pending_plugin_requirement_removals() -> list[str]:
    """Return package requirements scheduled for deferred removal."""
    return _read_pending_plugin_uninstalls()


def discard_plugin_requirement_removal(requirement: str) -> bool:
    """Remove one scheduled package requirement removal marker."""
    target = resolve_declared_plugin_requirement(requirement).strip()
    if not target:
        return False

    pending = _read_pending_plugin_uninstalls()
    normalized_target = normalize_package_id(target) or target
    remaining = [
        item
        for item in pending
        if (normalize_package_id(item) or item) != normalized_target
    ]
    if len(remaining) == len(pending):
        return False
    _write_pending_plugin_uninstalls(remaining)
    return True


def enqueue_plugin_module_uninstall(module_name: str) -> bool:
    """Mark a loaded plugin module as pending removal until restart."""
    target = module_name.strip()
    if not target:
        return False

    pending = _read_pending_plugin_module_uninstalls()
    if target in pending:
        return False

    pending.append(target)
    _write_pending_plugin_module_uninstalls(pending)
    return True


def pending_plugin_module_uninstalls() -> list[str]:
    """Return plugin module names scheduled for deferred unload."""
    return _read_pending_plugin_module_uninstalls()


def discard_plugin_module_uninstall(module_name: str) -> bool:
    """Remove one scheduled module removal marker."""
    target = module_name.strip()
    if not target:
        return False

    pending = _read_pending_plugin_module_uninstalls()
    remaining = [item for item in pending if item != target]
    if len(remaining) == len(pending):
        return False
    _write_pending_plugin_module_uninstalls(remaining)
    return True


def process_pending_plugin_module_uninstalls() -> list[str]:
    """Consume deferred module removal markers after a process restart."""
    pending = _read_pending_plugin_module_uninstalls()
    if not pending:
        return []
    _write_pending_plugin_module_uninstalls([])
    return pending


def declared_plugin_requirements() -> dict[str, str]:
    """Return normalized dependency names mapped to declared requirement strings."""
    pyproject_path = plugin_project_pyproject_path()
    toml_module = _load_toml_module()
    if toml_module is None:
        return {}
    try:
        with pyproject_path.open("rb") as file:
            data = toml_module.load(file)
    except (OSError, ValueError):
        return {}

    project = data.get("project")
    if not isinstance(project, dict):
        return {}

    dependencies = project.get("dependencies")
    if not isinstance(dependencies, list):
        return {}

    declared: dict[str, str] = {}
    for item in dependencies:
        if not isinstance(item, str):
            continue
        normalized = normalize_package_id(item)
        if normalized:
            declared[normalized] = item
    return declared


def resolve_declared_plugin_requirement(requirement: str) -> str:
    normalized = normalize_package_id(requirement)
    if not normalized:
        return requirement
    return declared_plugin_requirements().get(normalized, requirement)


def process_pending_plugin_requirement_removals() -> list[str]:
    pending = _read_pending_plugin_uninstalls()
    if not pending:
        return []

    processed: list[str] = []
    remaining: list[str] = []
    for requirement in pending:
        declared = resolve_declared_plugin_requirement(requirement).strip()
        if not declared:
            continue
        normalized = normalize_package_id(declared)
        if normalized not in declared_plugin_requirements():
            continue
        try:
            remove_plugin_requirement(declared)
        except RuntimeError as exc:
            _logger.warning(
                "deferred plugin uninstall failed for %s: %s",
                declared,
                exc,
            )
            remaining.append(requirement)
            continue
        processed.append(declared)

    _write_pending_plugin_uninstalls(remaining)
    return processed


def plugin_site_packages_paths() -> list[Path]:
    venv = plugin_project_venv_path()
    if not venv.exists():
        return []

    candidates = [
        path
        for pattern in ("lib/python*/site-packages", "Lib/site-packages")
        for path in venv.glob(pattern)
    ]
    return [path.resolve() for path in candidates if path.is_dir()]


def inject_plugin_site_packages() -> list[Path]:
    """Expose extension site-packages to the current interpreter process.

    This keeps NoneBot able to import plugins, adapters, and drivers installed
    into the managed extension environment without activating that venv.
    """
    added: list[Path] = []
    for path in plugin_site_packages_paths():
        if str(path) in site.getsitepackages():
            continue
        if str(path) in sys.path:
            continue
        site.addsitedir(str(path))
        _extend_loaded_nonebot_package(path)
        added.append(path)
    return added


def _extend_loaded_nonebot_package(site_packages: Path) -> None:
    """Extend already-imported NoneBot namespace packages with extension paths."""
    _extend_loaded_package_path("nonebot", site_packages / "nonebot")
    _extend_loaded_package_path(
        "nonebot.adapters",
        site_packages / "nonebot" / "adapters",
    )
    _extend_loaded_package_path(
        "nonebot.drivers",
        site_packages / "nonebot" / "drivers",
    )


def _extend_loaded_package_path(module_name: str, package_dir: Path) -> None:
    module = sys.modules.get(module_name)
    if module is None or not package_dir.is_dir():
        return

    package_path = getattr(module, "__path__", None)
    if package_path is None:
        return

    normalized = str(package_dir)
    if normalized not in package_path:
        package_path.append(normalized)


def _read_pending_plugin_uninstalls() -> list[str]:
    path = plugin_pending_uninstalls_path()
    return _read_pending_json_items(path)


def _write_pending_plugin_uninstalls(requirements: list[str]) -> None:
    _write_pending_json_items(plugin_pending_uninstalls_path(), requirements)


def _read_pending_plugin_module_uninstalls() -> list[str]:
    path = plugin_pending_module_uninstalls_path()
    return _read_pending_json_items(path)


def _write_pending_plugin_module_uninstalls(module_names: list[str]) -> None:
    _write_pending_json_items(plugin_pending_module_uninstalls_path(), module_names)


def _read_pending_json_items(path: Path) -> list[str]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    if not isinstance(payload, list):
        return []
    return [item.strip() for item in payload if isinstance(item, str) and item.strip()]


def _write_pending_json_items(path: Path, items: list[str]) -> None:
    normalized = [
        item.strip() for item in items if isinstance(item, str) and item.strip()
    ]
    if not normalized:
        try:
            path.unlink()
        except FileNotFoundError:
            return
        return
    atomic_write_text(
        path,
        json.dumps(normalized, ensure_ascii=True, indent=2) + "\n",
    )

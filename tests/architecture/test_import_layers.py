from __future__ import annotations

import ast
from dataclasses import dataclass
from importlib.util import resolve_name
from pathlib import Path

from apeiria.runtime.package_map import (
    APP_PREFIXES,
    PLANNED_APP_NAMESPACE_MOVES,
    STABLE_ROOT_BOUNDARY_EXCLUSIONS,
    STABLE_ROOT_PREFIXES,
    SURFACE_PREFIXES,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class ImportViolation:
    source_module: str
    imported_module: str


def test_stable_roots_do_not_import_app_surfaces_or_runtime() -> None:
    violations = _collect_boundary_violations(
        source_prefixes=STABLE_ROOT_PREFIXES,
        forbidden_prefixes=APP_PREFIXES + SURFACE_PREFIXES + ("apeiria.runtime",),
        excluded_prefixes=STABLE_ROOT_BOUNDARY_EXCLUSIONS,
    )

    assert not violations, _format_violations(
        "stable roots importing app/surface/runtime modules",
        violations,
    )


def test_app_packages_do_not_import_surfaces_or_runtime() -> None:
    violations = _collect_boundary_violations(
        source_prefixes=APP_PREFIXES,
        forbidden_prefixes=(*SURFACE_PREFIXES, "apeiria.runtime"),
    )

    assert not violations, _format_violations(
        "app packages importing surface/runtime modules",
        violations,
    )


def test_surface_packages_do_not_import_retired_app_owned_namespaces() -> None:
    violations = _collect_boundary_violations(
        source_prefixes=SURFACE_PREFIXES,
        forbidden_prefixes=tuple(
            source_prefix
            for source_prefix, _target_prefix in PLANNED_APP_NAMESPACE_MOVES
        ),
    )

    assert not violations, _format_violations(
        "surface packages importing retired app-owned namespaces",
        violations,
    )


def test_ai_routes_do_not_import_removed_catch_all_surface_modules() -> None:
    violations = _collect_boundary_violations(
        source_prefixes=("apeiria.webui.routes.ai",),
        forbidden_prefixes=(
            "apeiria.webui.routes.ai.schemas",
            "apeiria.webui.routes.ai.support",
            "apeiria.webui.routes.ai.session_support",
        ),
    )

    assert not violations, _format_violations(
        "AI routes importing removed catch-all surface modules",
        violations,
    )


def test_ai_model_capability_uses_subdomain_packages() -> None:
    expected_packages = (
        REPO_ROOT / "apeiria/ai/model/sources",
        REPO_ROOT / "apeiria/ai/model/catalog",
        REPO_ROOT / "apeiria/ai/model/routing",
        REPO_ROOT / "apeiria/ai/model/runtime",
    )
    missing_packages = tuple(
        str(path.relative_to(REPO_ROOT))
        for path in expected_packages
        if not path.is_dir()
    )
    assert not missing_packages

    retired_flat_modules = (
        "adapter.py",
        "bindings.py",
        "capability_registry.py",
        "capability_selection.py",
        "chat_model.py",
        "chat_models.py",
        "client.py",
        "embedding_model.py",
        "factory.py",
        "gateway.py",
        "models.py",
        "profile.py",
        "rerank_model.py",
        "routing.py",
        "selection.py",
        "service.py",
        "source.py",
        "source_model_storage.py",
        "source_models.py",
        "sources.py",
        "stt_model.py",
        "tts_model.py",
    )
    lingering_modules = tuple(
        f"apeiria/ai/model/{module_name}"
        for module_name in retired_flat_modules
        if (REPO_ROOT / "apeiria/ai/model" / module_name).exists()
    )
    assert not lingering_modules


def test_plugin_routes_do_not_import_plugin_buckets_from_shared_models() -> None:
    violations = _collect_boundary_violations(
        source_prefixes=(
            "apeiria.webui.routes.plugin_catalog",
            "apeiria.webui.routes.plugin_config",
            "apeiria.webui.routes.plugin_management",
            "apeiria.webui.routes.plugin_store",
        ),
        forbidden_prefixes=(
            "apeiria.webui.routes.plugin_support",
            "apeiria.webui.schemas.models",
        ),
    )

    assert not violations, _format_violations(
        "plugin routes importing plugin DTO/helper buckets",
        violations,
    )


def test_management_webui_routes_do_not_import_displaced_management_services() -> None:
    violations = _collect_boundary_violations(
        source_prefixes=(
            "apeiria.webui.routes.plugin_catalog",
            "apeiria.webui.routes.plugin_config",
            "apeiria.webui.routes.plugin_management",
            "apeiria.webui.routes.access",
            "apeiria.webui.routes.dashboard",
        ),
        forbidden_prefixes=(
            "apeiria.plugins",
            "apeiria.access",
            "apeiria.environment",
        ),
    )

    assert not violations, _format_violations(
        "management webui routes importing displaced management services",
        violations,
    )


def test_builtin_admin_surfaces_do_not_import_displaced_management_services() -> None:
    violations = _collect_boundary_violations(
        source_prefixes=(
            "apeiria.builtin_plugins.admin.access_admin",
            "apeiria.builtin_plugins.admin.adapters",
            "apeiria.builtin_plugins.admin.config_view",
            "apeiria.builtin_plugins.admin.drivers",
            "apeiria.builtin_plugins.admin.overview",
            "apeiria.builtin_plugins.admin.plugin_admin",
            "apeiria.builtin_plugins.admin.restart",
            "apeiria.builtin_plugins.admin.status",
            "apeiria.builtin_plugins.admin.utils",
        ),
        forbidden_prefixes=(
            "apeiria.plugins",
            "apeiria.access",
            "apeiria.environment",
        ),
    )

    assert not violations, _format_violations(
        "builtin admin surfaces importing displaced management services",
        violations,
    )


def _collect_boundary_violations(
    *,
    source_prefixes: tuple[str, ...],
    forbidden_prefixes: tuple[str, ...],
    excluded_prefixes: tuple[str, ...] = (),
) -> list[ImportViolation]:
    violations: list[ImportViolation] = []
    for source_prefix in source_prefixes:
        for module_name, path in _iter_python_modules(
            source_prefix,
            excluded_prefixes=excluded_prefixes,
        ):
            violations.extend(
                ImportViolation(
                    source_module=module_name,
                    imported_module=imported_module,
                )
                for imported_module in _iter_imported_modules(module_name, path)
                if _matches_any(imported_module, forbidden_prefixes)
            )
    return violations


def _iter_python_modules(
    source_prefix: str,
    *,
    excluded_prefixes: tuple[str, ...],
) -> list[tuple[str, Path]]:
    source_path = REPO_ROOT / source_prefix.replace(".", "/")
    module_file_path = source_path.with_suffix(".py")
    if module_file_path.is_file():
        module_name = source_prefix
        if _matches_any(module_name, excluded_prefixes):
            return []
        return [(module_name, module_file_path)]
    if source_path.is_file():
        module_name = source_prefix.removesuffix(".py")
        if _matches_any(module_name, excluded_prefixes):
            return []
        return [(module_name, source_path)]

    modules: list[tuple[str, Path]] = []
    if not source_path.exists():
        return modules

    for path in sorted(source_path.rglob("*.py")):
        module_name = _module_name_for_path(path)
        if _matches_any(module_name, excluded_prefixes):
            continue
        modules.append((module_name, path))
    return modules


def _module_name_for_path(path: Path) -> str:
    relative_path = path.relative_to(REPO_ROOT).with_suffix("")
    parts = list(relative_path.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _iter_imported_modules(module_name: str, path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    current_package = (
        module_name if path.name == "__init__.py" else module_name.rsplit(".", 1)[0]
    )
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_module = _resolve_import_from(node, current_package)
            if imported_module is not None:
                imports.append(imported_module)
    return imports


def _resolve_import_from(node: ast.ImportFrom, current_package: str) -> str | None:
    if node.level == 0:
        return node.module

    relative_target = "." * node.level
    if node.module is not None:
        relative_target += node.module
    try:
        return resolve_name(relative_target, current_package)
    except ImportError:
        return None


def _matches_any(module_name: str, prefixes: tuple[str, ...]) -> bool:
    return any(
        module_name == prefix or module_name.startswith(prefix + ".")
        for prefix in prefixes
    )


def _format_violations(title: str, violations: list[ImportViolation]) -> str:
    details = "\n".join(
        f"- {violation.source_module} -> {violation.imported_module}"
        for violation in violations
    )
    return f"Forbidden imports detected for {title}:\n{details}"

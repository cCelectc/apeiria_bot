"""Reusable adapter and driver store operations for the CLI."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import Distribution, distributions
from pathlib import PurePosixPath
from typing import Literal

from apeiria.app.plugin_store.package_ops import (
    StoreInstallError,
)
from apeiria.infra.config.adapters import adapter_config_service
from apeiria.infra.config.drivers import driver_config_service
from apeiria.infra.runtime.environment import (
    add_plugin_requirement,
    declared_plugin_requirements,
    plugin_site_packages_paths,
    remove_plugin_requirement,
)
from apeiria.package_ids import normalize_package_id


@dataclass(frozen=True)
class AdapterInstallResult:
    """Result of one adapter install operation."""

    requirement: str
    module_name: str


@dataclass(frozen=True)
class AdapterUninstallResult:
    """Result of one adapter uninstall operation."""

    requirement: str
    module_names: list[str]


@dataclass(frozen=True)
class DriverInstallResult:
    """Result of one driver install operation."""

    requirement: str
    builtin_name: str


@dataclass(frozen=True)
class DriverUninstallResult:
    """Result of one driver uninstall operation."""

    requirement: str
    builtin_names: list[str]


@dataclass(frozen=True)
class AdapterUninstallRollbackPlan:
    """Rollback information for one adapter uninstall operation."""

    removed_requirement: bool
    restore_package_binding: bool


@dataclass(frozen=True)
class DriverUninstallRollbackPlan:
    """Rollback information for one driver uninstall operation."""

    removed_requirement: bool
    restore_package_binding: bool


ResourceKind = Literal["plugin", "adapter", "driver"]
PLUGIN_PART_COUNT_MIN = 2
NAMESPACE_PART_COUNT_MIN = 3


def _missing_package_name_error() -> StoreInstallError:
    return StoreInstallError("package name is required")


def _missing_adapter_module_name_error() -> StoreInstallError:
    return StoreInstallError("adapter module name is required")


def _missing_driver_builtin_name_error() -> StoreInstallError:
    return StoreInstallError("driver builtin name is required")


def _automatic_resolution_error(kind: ResourceKind) -> StoreInstallError:
    if kind == "plugin":
        return StoreInstallError(
            "could not determine plugin module automatically; use --module"
        )
    if kind == "adapter":
        return StoreInstallError(
            "could not determine adapter module automatically; use --module"
        )
    return StoreInstallError(
        "could not determine driver builtin automatically; use --builtin"
    )


def install_adapter_package(
    requirement: str,
    module_name: str,
    extra_args: tuple[str, ...] = (),
) -> AdapterInstallResult:
    """Install an adapter package and bind its module into project config."""

    target = requirement.strip()
    resolved_module = module_name.strip()
    if not target:
        raise _missing_package_name_error()
    if not resolved_module:
        raise _missing_adapter_module_name_error()

    try:
        add_plugin_requirement(target, extra_args)
    except RuntimeError as exc:
        raise StoreInstallError(str(exc)) from exc

    try:
        adapter_config_service.bind_project_adapter_package(target, resolved_module)
    except Exception as exc:
        _rollback_adapter_install(target, extra_args, exc)
        raise AssertionError("unreachable") from exc

    return AdapterInstallResult(
        requirement=target,
        module_name=resolved_module,
    )


def install_adapter_requirement_with_auto_module(
    requirement: str,
    extra_args: tuple[str, ...] = (),
) -> AdapterInstallResult:
    """Install an adapter requirement and infer its module automatically."""

    target = requirement.strip()
    if not target:
        raise _missing_package_name_error()

    declared_before = declared_plugin_requirements()
    distributions_before = _installed_distributions_by_name()
    try:
        add_plugin_requirement(target, extra_args)
    except RuntimeError as exc:
        raise StoreInstallError(str(exc)) from exc

    declared_requirement = _resolve_declared_requirement(target, declared_before)
    try:
        resolved_module = _infer_adapter_module(
            target,
            declared_requirement,
            distributions_before,
        )
        adapter_config_service.bind_project_adapter_package(
            declared_requirement,
            resolved_module,
        )
    except Exception as exc:
        _rollback_adapter_install(declared_requirement, extra_args, exc)
        raise AssertionError("unreachable") from exc

    return AdapterInstallResult(
        requirement=declared_requirement,
        module_name=resolved_module,
    )


def uninstall_adapter_package(
    requirement: str,
    module_name: str,
    extra_args: tuple[str, ...] = (),
) -> AdapterUninstallResult:
    """Uninstall or unbind one adapter module from a package."""

    target = requirement.strip()
    resolved_module = module_name.strip()
    if not target:
        raise _missing_package_name_error()
    if not resolved_module:
        raise _missing_adapter_module_name_error()

    registered_modules = adapter_config_service.get_project_adapter_package_modules(
        target
    )
    package_was_bound = bool(registered_modules)
    if package_was_bound and resolved_module not in registered_modules:
        msg = f"module {resolved_module} is not bound to package {target}"
        raise StoreInstallError(msg)

    removed_requirement = not package_was_bound or len(registered_modules) == 1

    if removed_requirement:
        try:
            remove_plugin_requirement(target, extra_args)
        except RuntimeError as exc:
            raise StoreInstallError(str(exc)) from exc

    try:
        adapter_config_service.remove_project_adapter_module(resolved_module)
    except Exception as exc:
        _rollback_adapter_uninstall(
            target,
            resolved_module,
            extra_args,
            exc,
            AdapterUninstallRollbackPlan(
                removed_requirement=removed_requirement,
                restore_package_binding=package_was_bound,
            ),
        )
        raise AssertionError("unreachable") from exc

    return AdapterUninstallResult(
        requirement=target,
        module_names=[resolved_module],
    )


def install_driver_package(
    requirement: str,
    builtin_name: str,
    extra_args: tuple[str, ...] = (),
) -> DriverInstallResult:
    """Install a driver package and bind its builtin into project config."""

    target = requirement.strip()
    resolved_builtin = builtin_name.strip()
    if not target:
        raise _missing_package_name_error()
    if not resolved_builtin:
        raise _missing_driver_builtin_name_error()

    try:
        add_plugin_requirement(target, extra_args)
    except RuntimeError as exc:
        raise StoreInstallError(str(exc)) from exc

    try:
        driver_config_service.bind_project_driver_package(target, resolved_builtin)
    except Exception as exc:
        _rollback_driver_install(target, extra_args, exc)
        raise AssertionError("unreachable") from exc

    return DriverInstallResult(
        requirement=target,
        builtin_name=resolved_builtin,
    )


def install_driver_requirement_with_auto_builtin(
    requirement: str,
    extra_args: tuple[str, ...] = (),
) -> DriverInstallResult:
    """Install a driver requirement and infer its builtin automatically."""

    target = requirement.strip()
    if not target:
        raise _missing_package_name_error()

    declared_before = declared_plugin_requirements()
    distributions_before = _installed_distributions_by_name()
    try:
        add_plugin_requirement(target, extra_args)
    except RuntimeError as exc:
        raise StoreInstallError(str(exc)) from exc

    declared_requirement = _resolve_declared_requirement(target, declared_before)
    try:
        resolved_builtin = _infer_driver_builtin(
            target,
            declared_requirement,
            distributions_before,
        )
        driver_config_service.bind_project_driver_package(
            declared_requirement,
            resolved_builtin,
        )
    except Exception as exc:
        _rollback_driver_install(declared_requirement, extra_args, exc)
        raise AssertionError("unreachable") from exc

    return DriverInstallResult(
        requirement=declared_requirement,
        builtin_name=resolved_builtin,
    )


def uninstall_driver_package(
    requirement: str,
    builtin_name: str,
    extra_args: tuple[str, ...] = (),
) -> DriverUninstallResult:
    """Uninstall or unbind one driver builtin from a package."""

    target = requirement.strip()
    resolved_builtin = builtin_name.strip()
    if not target:
        raise _missing_package_name_error()
    if not resolved_builtin:
        raise _missing_driver_builtin_name_error()

    registered_builtin = driver_config_service.get_project_driver_package_builtin(
        target
    )
    package_was_bound = bool(registered_builtin)
    if package_was_bound and resolved_builtin not in registered_builtin:
        msg = f"builtin {resolved_builtin} is not bound to package {target}"
        raise StoreInstallError(msg)

    removed_requirement = not package_was_bound or len(registered_builtin) == 1

    if removed_requirement:
        try:
            remove_plugin_requirement(target, extra_args)
        except RuntimeError as exc:
            raise StoreInstallError(str(exc)) from exc

    try:
        driver_config_service.remove_project_driver_builtin(resolved_builtin)
    except Exception as exc:
        _rollback_driver_uninstall(
            target,
            resolved_builtin,
            extra_args,
            exc,
            DriverUninstallRollbackPlan(
                removed_requirement=removed_requirement,
                restore_package_binding=package_was_bound,
            ),
        )
        raise AssertionError("unreachable") from exc

    return DriverUninstallResult(
        requirement=target,
        builtin_names=[resolved_builtin],
    )


def _rollback_adapter_install(
    target: str,
    extra_args: tuple[str, ...],
    exc: Exception,
) -> None:
    try:
        remove_plugin_requirement(target, extra_args)
    except RuntimeError as rollback_exc:
        msg = (
            f"{exc}\n"
            "rollback failed: "
            f"{target} is still installed in the extension environment\n"
            f"{rollback_exc}"
        )
        raise StoreInstallError(msg) from rollback_exc
    raise StoreInstallError(str(exc)) from exc


def _rollback_adapter_uninstall(
    target: str,
    module_name: str,
    extra_args: tuple[str, ...],
    exc: Exception,
    plan: AdapterUninstallRollbackPlan,
) -> None:
    try:
        if plan.removed_requirement:
            add_plugin_requirement(target, extra_args)
        if plan.restore_package_binding:
            adapter_config_service.bind_project_adapter_package(target, module_name)
        else:
            adapter_config_service.add_project_adapter_module(module_name)
    except Exception as rollback_exc:
        msg = (
            f"{exc}\n"
            "rollback failed: "
            f"{target} could not be restored to its previous state\n"
            f"{rollback_exc}"
        )
        raise StoreInstallError(msg) from rollback_exc
    raise StoreInstallError(str(exc)) from exc


def _rollback_driver_install(
    target: str,
    extra_args: tuple[str, ...],
    exc: Exception,
) -> None:
    try:
        remove_plugin_requirement(target, extra_args)
    except RuntimeError as rollback_exc:
        msg = (
            f"{exc}\n"
            "rollback failed: "
            f"{target} is still installed in the extension environment\n"
            f"{rollback_exc}"
        )
        raise StoreInstallError(msg) from rollback_exc
    raise StoreInstallError(str(exc)) from exc


def _rollback_driver_uninstall(
    target: str,
    builtin_name: str,
    extra_args: tuple[str, ...],
    exc: Exception,
    plan: DriverUninstallRollbackPlan,
) -> None:
    try:
        if plan.removed_requirement:
            add_plugin_requirement(target, extra_args)
        if plan.restore_package_binding:
            driver_config_service.bind_project_driver_package(target, builtin_name)
        else:
            driver_config_service.add_project_driver_builtin(builtin_name)
    except Exception as rollback_exc:
        msg = (
            f"{exc}\n"
            "rollback failed: "
            f"{target} could not be restored to its previous state\n"
            f"{rollback_exc}"
        )
        raise StoreInstallError(msg) from rollback_exc
    raise StoreInstallError(str(exc)) from exc


def _resolve_declared_requirement(
    target: str,
    before: dict[str, str],
) -> str:
    current = declared_plugin_requirements()
    normalized_target = normalize_package_id(target)
    if normalized_target and normalized_target in current:
        return current[normalized_target]

    changed = {
        name: requirement
        for name, requirement in current.items()
        if before.get(name) != requirement
    }
    if len(changed) == 1:
        return next(iter(changed.values()))
    return target


def _installed_distributions_by_name() -> dict[str, Distribution]:
    paths = [str(path) for path in plugin_site_packages_paths()]
    installed: dict[str, Distribution] = {}
    if not paths:
        return installed
    for dist in distributions(path=paths):
        try:
            raw_name = dist.metadata["Name"]
        except KeyError:
            raw_name = ""
        name = normalize_package_id(raw_name)
        if name:
            installed[name] = dist
    return installed


def _infer_plugin_module(
    raw_requirement: str,
    declared_requirement: str,
    distributions_before: dict[str, Distribution],
) -> str:
    candidates = _collect_plugin_candidates(
        raw_requirement,
        declared_requirement,
        distributions_before,
    )
    return _require_single_candidate("plugin", candidates)


def _infer_adapter_module(
    raw_requirement: str,
    declared_requirement: str,
    distributions_before: dict[str, Distribution],
) -> str:
    candidates = _collect_adapter_candidates(
        raw_requirement,
        declared_requirement,
        distributions_before,
    )
    return _require_single_candidate("adapter", candidates)


def _infer_driver_builtin(
    raw_requirement: str,
    declared_requirement: str,
    distributions_before: dict[str, Distribution],
) -> str:
    candidates = _collect_driver_candidates(
        raw_requirement,
        declared_requirement,
        distributions_before,
    )
    return _require_single_candidate("driver", candidates)


def _require_single_candidate(kind: ResourceKind, values: list[str]) -> str:
    unique_values = sorted({value.strip() for value in values if value.strip()})
    if len(unique_values) == 1:
        return unique_values[0]
    raise _automatic_resolution_error(kind)


def _collect_plugin_candidates(
    raw_requirement: str,
    declared_requirement: str,
    distributions_before: dict[str, Distribution],
) -> list[str]:
    candidates: list[str] = []
    for value in (declared_requirement, raw_requirement):
        candidates.extend(_plugin_candidates_from_requirement(value))
    for dist in _primary_distributions(
        declared_requirement,
        distributions_before,
    ):
        candidates.extend(_plugin_candidates_from_distribution(dist))
    return candidates


def _collect_adapter_candidates(
    raw_requirement: str,
    declared_requirement: str,
    distributions_before: dict[str, Distribution],
) -> list[str]:
    candidates: list[str] = []
    for value in (declared_requirement, raw_requirement):
        candidates.extend(_adapter_candidates_from_requirement(value))
    for dist in _primary_distributions(
        declared_requirement,
        distributions_before,
    ):
        candidates.extend(_adapter_candidates_from_distribution(dist))
    return candidates


def _collect_driver_candidates(
    raw_requirement: str,
    declared_requirement: str,
    distributions_before: dict[str, Distribution],
) -> list[str]:
    candidates: list[str] = []
    for value in (declared_requirement, raw_requirement):
        candidates.extend(_driver_candidates_from_requirement(value))
    for dist in _primary_distributions(
        declared_requirement,
        distributions_before,
    ):
        candidates.extend(_driver_candidates_from_distribution(dist))
    return candidates


def _primary_distributions(
    declared_requirement: str,
    distributions_before: dict[str, Distribution],
) -> list[Distribution]:
    current = _installed_distributions_by_name()
    normalized_requirement = normalize_package_id(declared_requirement)
    if normalized_requirement and normalized_requirement in current:
        return [current[normalized_requirement]]

    new_names = sorted(set(current) - set(distributions_before))
    return [current[name] for name in new_names]


def _plugin_candidates_from_requirement(requirement: str) -> list[str]:
    normalized = normalize_package_id(requirement)
    if normalized.startswith("nonebot-plugin-"):
        suffix = normalized.removeprefix("nonebot-plugin-").replace("-", "_")
        if suffix:
            return [f"nonebot_plugin_{suffix}"]
    return []


def _adapter_candidates_from_requirement(requirement: str) -> list[str]:
    normalized = normalize_package_id(requirement)
    if normalized.startswith("nonebot-adapter-"):
        suffix = normalized.removeprefix("nonebot-adapter-").replace("-", "_")
        if suffix:
            return [f"nonebot.adapters.{suffix}"]
    return []


def _driver_candidates_from_requirement(requirement: str) -> list[str]:
    normalized = normalize_package_id(requirement)
    if normalized.startswith("nonebot-driver-"):
        suffix = normalized.removeprefix("nonebot-driver-").replace("-", "_")
        if suffix:
            return [f"~{suffix}"]
    return []


def _plugin_candidates_from_distribution(dist: Distribution) -> list[str]:
    candidates: list[str] = []
    top_level = dist.read_text("top_level.txt") or ""
    for line in top_level.splitlines():
        module_name = line.strip()
        if module_name.startswith("nonebot_plugin_"):
            candidates.append(module_name)
    for file in dist.files or []:
        parts = PurePosixPath(str(file)).parts
        if not parts:
            continue
        if parts[0].endswith(".dist-info"):
            continue
        if len(parts) >= PLUGIN_PART_COUNT_MIN and parts[0].startswith(
            "nonebot_plugin_"
        ):
            candidates.append(parts[0])
        elif parts[0].startswith("nonebot_plugin_") and parts[0].endswith(".py"):
            candidates.append(parts[0][:-3])
    return candidates


def _adapter_candidates_from_distribution(dist: Distribution) -> list[str]:
    candidates: list[str] = []
    for file in dist.files or []:
        parts = PurePosixPath(str(file)).parts
        if len(parts) < NAMESPACE_PART_COUNT_MIN:
            continue
        if parts[0] != "nonebot" or parts[1] != "adapters":
            continue
        name = parts[2]
        if name.endswith(".py"):
            candidates.append(f"nonebot.adapters.{name[:-3]}")
            continue
        candidates.append(f"nonebot.adapters.{name}")
    return candidates


def _driver_candidates_from_distribution(dist: Distribution) -> list[str]:
    candidates: list[str] = []
    for file in dist.files or []:
        parts = PurePosixPath(str(file)).parts
        if len(parts) < NAMESPACE_PART_COUNT_MIN:
            continue
        if parts[0] != "nonebot" or parts[1] != "drivers":
            continue
        name = parts[2]
        if name.endswith(".py"):
            candidates.append(f"~{name[:-3]}")
            continue
        candidates.append(f"~{name}")
    return candidates

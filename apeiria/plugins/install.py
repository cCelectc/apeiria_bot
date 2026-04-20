"""Operations-plane package service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import Distribution, distributions
from pathlib import PurePosixPath

from apeiria.config.adapters import adapter_config_service
from apeiria.config.drivers import driver_config_service
from apeiria.config.plugins import plugin_config_service
from apeiria.environment.extension_project import (
    add_plugin_requirement,
    declared_plugin_requirements,
    discard_plugin_module_uninstall,
    discard_plugin_requirement_removal,
    plugin_site_packages_paths,
    remove_plugin_requirement,
    update_plugin_requirement,
)
from apeiria.environment.models import (
    PackageOperationRequest,
    PackageOperationResult,
    ResourceKind,
)
from apeiria.plugins.package_ids import normalize_package_id


def _invalidate_plugin_caches() -> None:
    from apeiria.utils.plugin_introspection import (
        invalidate_plugin_management_caches,
    )

    invalidate_plugin_management_caches()


BindRequirement = Callable[[str, str], object]
RemoveBinding = Callable[[str], object]
AddBinding = Callable[[str], object]
GetBoundItems = Callable[[str], list[str]]
CandidatesFromRequirement = Callable[[str], list[str]]
CandidatesFromDistribution = Callable[[Distribution], list[str]]
AfterMutation = Callable[[str, str | None], None]

PLUGIN_PART_COUNT_MIN = 2
NAMESPACE_PART_COUNT_MIN = 3


class StoreInstallError(RuntimeError):
    """Raised when one package operation fails."""


@dataclass(frozen=True)
class _UninstallRollbackPlan:
    removed_requirement: bool
    restore_package_binding: bool


@dataclass(frozen=True)
class _UninstallRollbackContext:
    requirement: str
    binding_value: str
    extra_args: tuple[str, ...]
    adapter: _PackageResourceAdapter
    plan: _UninstallRollbackPlan


@dataclass(frozen=True)
class _PackageResourceAdapter:
    resource_kind: ResourceKind
    binding_label: str
    cli_hint: str
    bind_requirement: BindRequirement
    remove_binding: RemoveBinding
    add_binding: AddBinding
    get_bound_items: GetBoundItems
    candidates_from_requirement: CandidatesFromRequirement
    candidates_from_distribution: CandidatesFromDistribution
    after_install: AfterMutation
    after_update: AfterMutation
    after_uninstall: AfterMutation


def _noop_after_mutation(requirement: str, binding_value: str | None) -> None:
    del requirement, binding_value


def _package_name_required_error() -> StoreInstallError:
    return StoreInstallError("package name is required")


def _package_not_registered_error(target: str) -> StoreInstallError:
    return StoreInstallError(f"package {target} is not registered in project config")


def _binding_not_bound_error(
    adapter: _PackageResourceAdapter,
    binding_value: str,
    target: str,
) -> StoreInstallError:
    return StoreInstallError(
        f"{adapter.binding_label} {binding_value} is not bound to package {target}"
    )


def _binding_required_error(adapter: _PackageResourceAdapter) -> StoreInstallError:
    return StoreInstallError(f"{adapter.binding_label} name is required")


def _automatic_resolution_error(
    adapter: _PackageResourceAdapter,
) -> StoreInstallError:
    return StoreInstallError(
        f"could not determine {adapter.binding_label} automatically; "
        f"use {adapter.cli_hint}"
    )


def _after_plugin_install(requirement: str, binding_value: str | None) -> None:
    discard_plugin_requirement_removal(requirement)
    if binding_value:
        discard_plugin_module_uninstall(binding_value)
    _invalidate_plugin_caches()


def _after_plugin_update(requirement: str, binding_value: str | None) -> None:
    discard_plugin_requirement_removal(requirement)
    if binding_value:
        discard_plugin_module_uninstall(binding_value)
    _invalidate_plugin_caches()


def _after_plugin_uninstall(requirement: str, binding_value: str | None) -> None:
    del requirement, binding_value
    _invalidate_plugin_caches()


class PackageService:
    """Stable package operation surface for CLI, Web UI, and future APIs."""

    def __init__(self) -> None:
        self._resource_adapters: dict[ResourceKind, _PackageResourceAdapter] = {
            "plugin": _PackageResourceAdapter(
                resource_kind="plugin",
                binding_label="plugin module",
                cli_hint="--module",
                bind_requirement=plugin_config_service.bind_project_plugin_package,
                remove_binding=plugin_config_service.remove_project_plugin_module,
                add_binding=plugin_config_service.add_project_plugin_module,
                get_bound_items=plugin_config_service.get_project_plugin_package_modules,
                candidates_from_requirement=_plugin_candidates_from_requirement,
                candidates_from_distribution=_plugin_candidates_from_distribution,
                after_install=_after_plugin_install,
                after_update=_after_plugin_update,
                after_uninstall=_after_plugin_uninstall,
            ),
            "adapter": _PackageResourceAdapter(
                resource_kind="adapter",
                binding_label="adapter module",
                cli_hint="--module",
                bind_requirement=adapter_config_service.bind_project_adapter_package,
                remove_binding=adapter_config_service.remove_project_adapter_module,
                add_binding=adapter_config_service.add_project_adapter_module,
                get_bound_items=adapter_config_service.get_project_adapter_package_modules,
                candidates_from_requirement=_adapter_candidates_from_requirement,
                candidates_from_distribution=_adapter_candidates_from_distribution,
                after_install=_noop_after_mutation,
                after_update=_noop_after_mutation,
                after_uninstall=_noop_after_mutation,
            ),
            "driver": _PackageResourceAdapter(
                resource_kind="driver",
                binding_label="driver builtin",
                cli_hint="--builtin",
                bind_requirement=driver_config_service.bind_project_driver_package,
                remove_binding=driver_config_service.remove_project_driver_builtin,
                add_binding=driver_config_service.add_project_driver_builtin,
                get_bound_items=driver_config_service.get_project_driver_package_builtin,
                candidates_from_requirement=_driver_candidates_from_requirement,
                candidates_from_distribution=_driver_candidates_from_distribution,
                after_install=_noop_after_mutation,
                after_update=_noop_after_mutation,
                after_uninstall=_noop_after_mutation,
            ),
        }

    def perform_operation(
        self,
        request: PackageOperationRequest,
    ) -> PackageOperationResult:
        if request.operation == "install":
            return self.install(request)
        if request.operation == "update":
            return self.update(request)
        if request.operation == "uninstall":
            return self.uninstall(request)
        msg = f"unsupported package operation: {request.operation}"
        raise ValueError(msg)

    def install(self, request: PackageOperationRequest) -> PackageOperationResult:
        target = request.requirement.strip()
        if not target:
            raise _package_name_required_error()
        if request.resource_kind == "package":
            self._add_requirement(target, request.extra_args)
            return PackageOperationResult(
                resource_kind=request.resource_kind,
                operation=request.operation,
                requirement=target,
                binding_values=[],
            )

        adapter = self._adapter_for(request.resource_kind)
        binding_value = (request.binding_value or "").strip()
        if binding_value:
            self._add_requirement(target, request.extra_args)
            try:
                adapter.bind_requirement(target, binding_value)
            except Exception as exc:
                self._rollback_install(target, request.extra_args, exc)
                raise AssertionError("unreachable") from exc
            adapter.after_install(target, binding_value)
            return PackageOperationResult(
                resource_kind=request.resource_kind,
                operation=request.operation,
                requirement=target,
                binding_values=[binding_value],
            )

        declared_before = declared_plugin_requirements()
        distributions_before = _installed_distributions_by_name()
        self._add_requirement(target, request.extra_args)
        declared_requirement = _resolve_declared_requirement(target, declared_before)
        try:
            resolved_binding = _infer_binding(
                adapter,
                raw_requirement=target,
                declared_requirement=declared_requirement,
                distributions_before=distributions_before,
            )
            adapter.bind_requirement(declared_requirement, resolved_binding)
        except Exception as exc:
            self._rollback_install(declared_requirement, request.extra_args, exc)
            raise AssertionError("unreachable") from exc
        adapter.after_install(declared_requirement, resolved_binding)
        return PackageOperationResult(
            resource_kind=request.resource_kind,
            operation=request.operation,
            requirement=declared_requirement,
            binding_values=[resolved_binding],
        )

    def update(self, request: PackageOperationRequest) -> PackageOperationResult:
        target = request.requirement.strip()
        if not target:
            raise _package_name_required_error()
        binding_value = (request.binding_value or "").strip()

        adapter: _PackageResourceAdapter | None = None
        if request.resource_kind != "package":
            adapter = self._adapter_for(request.resource_kind)
            if binding_value:
                registered_items = adapter.get_bound_items(target)
                if not registered_items:
                    raise _package_not_registered_error(target)
                if binding_value not in registered_items:
                    raise _binding_not_bound_error(adapter, binding_value, target)

        try:
            update_plugin_requirement(target, request.extra_args)
        except RuntimeError as exc:
            raise StoreInstallError(str(exc)) from exc

        if adapter is not None:
            adapter.after_update(target, binding_value or None)

        return PackageOperationResult(
            resource_kind=request.resource_kind,
            operation=request.operation,
            requirement=target,
            binding_values=[binding_value] if binding_value else [],
        )

    def uninstall(self, request: PackageOperationRequest) -> PackageOperationResult:
        target = request.requirement.strip()
        if not target:
            raise _package_name_required_error()
        if request.resource_kind == "package":
            try:
                remove_plugin_requirement(target, request.extra_args)
            except RuntimeError as exc:
                raise StoreInstallError(str(exc)) from exc
            return PackageOperationResult(
                resource_kind=request.resource_kind,
                operation=request.operation,
                requirement=target,
                binding_values=[],
            )

        adapter = self._adapter_for(request.resource_kind)
        registered_items = adapter.get_bound_items(target)
        binding_value = (request.binding_value or "").strip()
        if not binding_value:
            if len(registered_items) == 1:
                binding_value = registered_items[0]
            else:
                raise _binding_required_error(adapter)
        package_was_bound = bool(registered_items)
        if package_was_bound and binding_value not in registered_items:
            raise _binding_not_bound_error(adapter, binding_value, target)

        removed_requirement = not package_was_bound or len(registered_items) == 1
        if removed_requirement:
            try:
                remove_plugin_requirement(target, request.extra_args)
            except RuntimeError as exc:
                raise StoreInstallError(str(exc)) from exc

        try:
            adapter.remove_binding(binding_value)
        except Exception as exc:
            self._rollback_uninstall(
                exc,
                _UninstallRollbackContext(
                    requirement=target,
                    binding_value=binding_value,
                    extra_args=request.extra_args,
                    adapter=adapter,
                    plan=_UninstallRollbackPlan(
                        removed_requirement=removed_requirement,
                        restore_package_binding=package_was_bound,
                    ),
                ),
            )
            raise AssertionError("unreachable") from exc

        adapter.after_uninstall(target, binding_value)
        return PackageOperationResult(
            resource_kind=request.resource_kind,
            operation=request.operation,
            requirement=target,
            binding_values=[binding_value],
        )

    def _adapter_for(self, resource_kind: ResourceKind) -> _PackageResourceAdapter:
        if resource_kind == "package":
            msg = "package resource does not use a binding adapter"
            raise ValueError(msg)
        return self._resource_adapters[resource_kind]

    def _add_requirement(
        self,
        requirement: str,
        extra_args: tuple[str, ...],
    ) -> None:
        try:
            add_plugin_requirement(requirement, extra_args)
        except RuntimeError as exc:
            raise StoreInstallError(str(exc)) from exc

    def _rollback_install(
        self,
        requirement: str,
        extra_args: tuple[str, ...],
        exc: Exception,
    ) -> None:
        try:
            remove_plugin_requirement(requirement, extra_args)
        except RuntimeError as rollback_exc:
            msg = (
                f"{exc}\n"
                "rollback failed: "
                f"{requirement} is still installed in the extension environment\n"
                f"{rollback_exc}"
            )
            raise StoreInstallError(msg) from rollback_exc
        raise StoreInstallError(str(exc)) from exc

    def _rollback_uninstall(
        self,
        exc: Exception,
        context: _UninstallRollbackContext,
    ) -> None:
        try:
            if context.plan.removed_requirement:
                add_plugin_requirement(context.requirement, context.extra_args)
            if context.plan.restore_package_binding:
                context.adapter.bind_requirement(
                    context.requirement,
                    context.binding_value,
                )
            else:
                context.adapter.add_binding(context.binding_value)
        except Exception as rollback_exc:
            msg = (
                f"{exc}\n"
                "rollback failed: "
                f"{context.requirement} could not be restored to its previous state\n"
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


def _infer_binding(
    adapter: _PackageResourceAdapter,
    *,
    raw_requirement: str,
    declared_requirement: str,
    distributions_before: dict[str, Distribution],
) -> str:
    candidates = _collect_candidates(
        adapter,
        raw_requirement=raw_requirement,
        declared_requirement=declared_requirement,
        distributions_before=distributions_before,
    )
    unique_values = sorted({value.strip() for value in candidates if value.strip()})
    if len(unique_values) == 1:
        return unique_values[0]
    raise _automatic_resolution_error(adapter)


def _collect_candidates(
    adapter: _PackageResourceAdapter,
    *,
    raw_requirement: str,
    declared_requirement: str,
    distributions_before: dict[str, Distribution],
) -> list[str]:
    candidates: list[str] = []
    for value in (declared_requirement, raw_requirement):
        candidates.extend(adapter.candidates_from_requirement(value))
    for distribution in _primary_distributions(
        declared_requirement,
        distributions_before,
    ):
        candidates.extend(adapter.candidates_from_distribution(distribution))
    return candidates


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
    target = requirement.strip()
    if not target:
        return []
    path_part = PurePosixPath(target.split("@", 1)[0].strip())
    candidate = path_part.name or path_part.parent.name
    candidate = candidate.replace("-", "_")
    return [candidate] if candidate else []


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
    candidates = _plugin_candidates_from_entry_points(dist)
    if candidates:
        return candidates

    return _plugin_candidates_from_top_level(dist) + _plugin_candidates_from_files(dist)


def _plugin_candidates_from_entry_points(dist: Distribution) -> list[str]:
    candidates: list[str] = []
    entry_points = list(getattr(dist, "entry_points", []) or [])
    for entry in entry_points:
        if getattr(entry, "group", "") != "nonebot.plugin":
            continue
        value = getattr(entry, "value", "")
        module_name = str(value).split(":", 1)[0].strip()
        if module_name:
            candidates.append(module_name)
    return candidates


def _plugin_candidates_from_top_level(dist: Distribution) -> list[str]:
    candidates: list[str] = []
    top_level = dist.read_text("top_level.txt") or ""
    for line in top_level.splitlines():
        module_name = line.strip()
        if module_name and not module_name.startswith("_"):
            candidates.append(module_name)
    return candidates


def _plugin_candidates_from_files(dist: Distribution) -> list[str]:
    candidates: list[str] = []
    for file in dist.files or []:
        parts = PurePosixPath(str(file)).parts
        if not parts or parts[0].endswith(".dist-info"):
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


package_service = PackageService()

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import click

from apeiria.infra.runtime.environment import resolve_declared_plugin_requirement

from .i18n import _
from .store import StoreInstallError
from .store_sources import resolve_cli_store_source

if TYPE_CHECKING:
    from .nb import MODULE_TYPE

InstallWithBinding = Callable[[str, str, tuple[str, ...]], object]
InstallWithAutoBinding = Callable[[str, tuple[str, ...]], object]
UninstallWithBinding = Callable[[str, str, tuple[str, ...]], object]
GetBoundItems = Callable[[str], list[str]]
SelectBoundValue = Callable[[object | None, str | None], str]
EnsureRemovable = Callable[[str], None]
InstalledPackageNames = Callable[[], list[str]]
PromptPackageName = Callable[[str, list[str]], str]
Fail = Callable[[str], None]


@dataclass(frozen=True)
class ResourceSpec:
    module_type: MODULE_TYPE
    missing_binding_message: str
    unbound_request_message: str
    install_with_binding: InstallWithBinding
    install_with_auto_binding: InstallWithAutoBinding
    uninstall_with_binding: UninstallWithBinding
    get_bound_items: GetBoundItems
    installed_package_names: InstalledPackageNames
    select_bound_value: SelectBoundValue
    ensure_removable: EnsureRemovable | None = None


def echo_store_packages(
    items: list[object],
    fail: Fail,
    source_id: str | None = None,
) -> str:
    if not items:
        return _("no store packages found")
    source = resolve_store_source(fail, source_id)
    return source.format_items(items)


def resolve_store_source(
    fail: Fail,
    source_id: str | None = None,
) -> Any:
    try:
        return resolve_cli_store_source(source_id)
    except RuntimeError as exc:
        if str(exc) == "nb-cli":
            fail(_("nb-cli is required for official store features"))
        if str(exc).startswith("unknown store source:"):
            fail(_("unknown store source: {source}").format(source=source_id or ""))
        raise


def store_packages(
    module_type: MODULE_TYPE,
    fail: Fail,
    query: str | None = None,
    source_id: str | None = None,
) -> list[object]:
    source = resolve_store_source(fail, source_id)
    try:
        return source.search(module_type, query)
    except RuntimeError as exc:
        if str(exc) == "nb-cli":
            fail(_("nb-cli is required for official store features"))
        raise


def exact_store_package(
    module_type: MODULE_TYPE,
    value: str,
    fail: Fail,
    source_id: str | None = None,
) -> object | None:
    source = resolve_store_source(fail, source_id)
    try:
        return source.find_exact(module_type, value)
    except RuntimeError as exc:
        if str(exc) == "nb-cli":
            fail(_("nb-cli is required for official store features"))
        raise


def select_store_package(
    module_type: MODULE_TYPE,
    fail: Fail,
    query: str | None = None,
    source_id: str | None = None,
) -> object:
    source = resolve_store_source(fail, source_id)
    try:
        return source.prompt_select(module_type, _("choose package"), query)
    except RuntimeError as exc:
        if str(exc) == "nb-cli":
            fail(_("nb-cli is required for official store features"))
        if str(exc) == "empty-store":
            fail(_("no store packages found"))
        fail(str(exc))
        raise
    except Exception as exc:
        if exc.__class__.__name__ == "CancelledError":
            raise click.Abort from exc
        raise


def explicit_install_requirement(
    package_name: str | None,
    requirement: str | None,
    *,
    use_store: bool,
    fail: Fail,
) -> str | None:
    explicit_requirement = requirement.strip() if requirement else ""
    if explicit_requirement:
        if use_store:
            fail(_("--store and --requirement cannot be used together"))
        if package_name:
            fail(_("package name cannot be used with --requirement"))
        return explicit_requirement
    return None


def declared_package_target(package_name: str) -> str:
    return resolve_declared_plugin_requirement(package_name)


def require_package_target(target: str | None, fail: Fail) -> str:
    if target:
        return target
    fail(_("package name is required"))
    raise AssertionError("unreachable")


def select_bound_items(
    bound_items: list[str],
    requested_item: str | None,
    *,
    missing_message: str,
    fail: Fail,
) -> list[str]:
    if not requested_item:
        return bound_items
    selected_item = requested_item.strip()
    if not selected_item:
        return bound_items
    if bound_items and selected_item not in bound_items:
        fail(missing_message)
    return [selected_item]


def resolve_install_request(  # noqa: PLR0913
    spec: ResourceSpec,
    package_name: str | None,
    binding_value: str | None,
    requirement: str | None,
    *,
    use_store: bool,
    source_id: str,
    fail: Fail,
    store_package_dependency: Callable[[object | None, str | None], str | None],
) -> tuple[str, str | None]:
    target = explicit_install_requirement(
        package_name,
        requirement,
        use_store=use_store,
        fail=fail,
    )
    package = None
    if target is None:
        package = (
            select_store_package(spec.module_type, fail, package_name, source_id)
            if use_store or not package_name
            else exact_store_package(spec.module_type, package_name, fail, source_id)
        )
        target = require_package_target(
            store_package_dependency(package, package_name),
            fail,
        )
    resolved_binding = (
        spec.select_bound_value(package, binding_value)
        if package is not None or binding_value
        else None
    )
    return target, resolved_binding


def run_install(
    spec: ResourceSpec,
    target: str,
    binding_value: str | None,
    pip_args: tuple[str, ...],
) -> str:
    try:
        if binding_value is not None:
            result = spec.install_with_binding(target, binding_value, pip_args)
        else:
            result = spec.install_with_auto_binding(target, pip_args)
    except StoreInstallError as exc:
        raise click.ClickException(str(exc)) from exc
    return str(getattr(result, "requirement", target))


def resolve_uninstall_bindings(
    spec: ResourceSpec,
    package_name: str,
    binding_value: str | None,
    *,
    fail: Fail,
    source_id: str | None = None,
) -> list[str]:
    target = declared_package_target(package_name)
    bound_items = spec.get_bound_items(target)
    if bound_items:
        return select_bound_items(
            bound_items,
            binding_value,
            missing_message=spec.unbound_request_message,
            fail=fail,
        )

    resolved_binding = binding_value.strip() if binding_value else ""
    if not resolved_binding:
        package = exact_store_package(spec.module_type, package_name, fail, source_id)
        resolved_binding = spec.select_bound_value(package, None)
    if not resolved_binding:
        fail(spec.missing_binding_message)
    return [resolved_binding]


def resolve_update_target(
    spec: ResourceSpec,
    package_name: str | None,
    *,
    prompt_package_name: PromptPackageName,
) -> str:
    selected_package = package_name or prompt_package_name(
        _("choose package"),
        spec.installed_package_names(),
    )
    return declared_package_target(selected_package)


def run_uninstall(
    spec: ResourceSpec,
    target: str,
    binding_values: list[str],
    pip_args: tuple[str, ...],
) -> None:
    if spec.ensure_removable is not None:
        for binding_value in binding_values:
            spec.ensure_removable(binding_value)
    try:
        for binding_value in binding_values:
            spec.uninstall_with_binding(target, binding_value, pip_args)
    except StoreInstallError as exc:
        raise click.ClickException(str(exc)) from exc

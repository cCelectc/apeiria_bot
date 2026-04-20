from __future__ import annotations

from pathlib import Path

import click

from apeiria.config import (
    adapter_config_service,
    driver_config_service,
    plugin_config_service,
)
from apeiria.environment import (
    PackageOperationRequest,
    StoreInstallError,
    package_service,
)
from apeiria.plugins.protection import is_protected_plugin_module

from .actions import (
    ResourceSpec,
    declared_package_target,
    echo_store_packages,
    exact_store_package,
    resolve_install_request,
    resolve_uninstall_bindings,
    resolve_update_target,
    run_install,
    run_uninstall,
    select_store_package,
    store_packages,
)
from .i18n import _
from .nb import MODULE_TYPE, prompt_select_text

add_project_adapter_module = adapter_config_service.add_project_adapter_module
default_adapter_config_path = adapter_config_service.default_config_path
ensure_project_adapter_config = adapter_config_service.ensure_project_adapter_config
get_project_adapter_package_modules = (
    adapter_config_service.get_project_adapter_package_modules
)
read_project_adapter_config = adapter_config_service.read_project_adapter_config
remove_project_adapter_module = adapter_config_service.remove_project_adapter_module

add_project_driver_builtin = driver_config_service.add_project_driver_builtin
default_driver_config_path = driver_config_service.default_config_path
ensure_project_driver_config = driver_config_service.ensure_project_driver_config
get_project_driver_kwargs = driver_config_service.get_project_driver_kwargs
get_project_driver_package_builtin = (
    driver_config_service.get_project_driver_package_builtin
)
read_project_driver_config = driver_config_service.read_project_driver_config
remove_project_driver_builtin = driver_config_service.remove_project_driver_builtin

add_project_plugin_dir = plugin_config_service.add_project_plugin_dir
add_project_plugin_module = plugin_config_service.add_project_plugin_module
default_plugin_config_path = plugin_config_service.default_config_path
ensure_project_plugin_config = plugin_config_service.ensure_project_plugin_config
get_project_plugin_package_modules = (
    plugin_config_service.get_project_plugin_package_modules
)
read_project_plugin_config = plugin_config_service.read_project_plugin_config
remove_project_plugin_dir = plugin_config_service.remove_project_plugin_dir
remove_project_plugin_module = plugin_config_service.remove_project_plugin_module


def config_path(path: str | None) -> Path | None:
    return Path(path).expanduser().resolve() if path else None


def current_config_path(config_file: Path | None, default_path: Path) -> Path:
    return default_path if config_file is None else config_file


def fail(message: str) -> None:
    raise click.ClickException(message)


def raise_click_runtime_error(exc: RuntimeError) -> None:
    raise click.ClickException(str(exc)) from exc


def ensure_single_listing_mode(
    *,
    installed: bool,
    registered: bool,
    use_store: bool,
) -> None:
    if sum([installed, registered, use_store]) > 1:
        fail(_("--installed, --registered and --store cannot be used together"))


def prompt_package_name(question: str, packages: list[str]) -> str:
    if not packages:
        raise click.ClickException(_("no installed packages available"))
    try:
        return prompt_select_text(question, packages)
    except RuntimeError as exc:
        if str(exc) != "nb-cli":
            raise
    except Exception as exc:
        if exc.__class__.__name__ == "CancelledError":
            raise click.Abort from exc
        raise
    click.echo(_("installed:"))
    for index, package_name in enumerate(packages, start=1):
        click.echo(f"  {index}. {package_name}")
    selected = click.prompt(question, type=click.IntRange(1, len(packages)))
    return packages[selected - 1]


def echo_store_packages_cli(
    items: list[object],
    source_id: str | None = None,
) -> None:
    click.echo(echo_store_packages(items, fail, source_id))


def store_packages_cli(
    module_type: MODULE_TYPE,
    query: str | None = None,
    source_id: str | None = None,
) -> list[object]:
    return store_packages(module_type, fail, query, source_id)


def echo_store_query(
    module_type: MODULE_TYPE,
    *,
    query: str | None = None,
    source_id: str | None = None,
) -> None:
    echo_store_packages_cli(
        store_packages_cli(module_type, query, source_id),
        source_id,
    )


def exact_store_package_cli(
    module_type: MODULE_TYPE,
    value: str,
    source_id: str | None = None,
) -> object | None:
    return exact_store_package(module_type, value, fail, source_id)


def select_store_package_cli(
    module_type: MODULE_TYPE,
    query: str | None = None,
    source_id: str | None = None,
) -> object:
    return select_store_package(module_type, fail, query, source_id)


def ensure_plugin_can_be_removed(module_name: str) -> None:
    if is_protected_plugin_module(module_name):
        fail(
            _("cannot remove protected plugin {module}: framework required").format(
                module=module_name
            )
        )


def echo_plugin_config(config_file: Path | None) -> None:
    config = read_project_plugin_config(config_file)
    current_path = current_config_path(config_file, default_plugin_config_path())
    click.echo(_("config: {path}").format(path=current_path))
    click.echo(_("modules:"))
    for module in config["modules"]:
        click.echo(f"  - {module}")
    click.echo(_("dirs:"))
    for directory in config["dirs"]:
        click.echo(f"  - {directory}")


def echo_installed_plugins(query: str | None = None) -> None:
    config = read_project_plugin_config()
    packages = sorted(config["packages"].items())
    if query:
        needle = query.lower()
        packages = [
            item
            for item in packages
            if needle in item[0].lower()
            or any(needle in module.lower() for module in item[1])
        ]
    if not packages:
        click.echo(_("no installed plugin packages found"))
        return
    click.echo(_("installed:"))
    modules_label = _("modules:")
    for name, modules in packages:
        click.echo(f"  - {name}")
        click.echo(f"    {modules_label} {', '.join(modules)}")


def installed_plugin_package_names() -> list[str]:
    return sorted(read_project_plugin_config()["packages"])


def echo_registered_plugins(
    config_file: Path | None,
    query: str | None = None,
) -> None:
    config = read_project_plugin_config(config_file)
    current_path = current_config_path(config_file, default_plugin_config_path())
    needle = (query or "").lower()
    modules = (
        [item for item in config["modules"] if needle in item.lower()]
        if needle
        else config["modules"]
    )
    dirs = (
        [item for item in config["dirs"] if needle in item.lower()]
        if needle
        else config["dirs"]
    )
    click.echo(_("registered:"))
    click.echo(_("config: {path}").format(path=current_path))
    click.echo(_("modules:"))
    for module in modules:
        click.echo(f"  - {module}")
    click.echo(_("dirs:"))
    for directory in dirs:
        click.echo(f"  - {directory}")


def echo_adapter_config(config_file: Path | None) -> None:
    config = read_project_adapter_config(config_file)
    current_path = current_config_path(config_file, default_adapter_config_path())
    click.echo(_("config: {path}").format(path=current_path))
    click.echo(_("modules:"))
    for module in config["modules"]:
        click.echo(f"  - {module}")


def echo_installed_adapters(query: str | None = None) -> None:
    config = read_project_adapter_config()
    packages = sorted(config["packages"].items())
    if query:
        needle = query.lower()
        packages = [
            item
            for item in packages
            if needle in item[0].lower()
            or any(needle in module.lower() for module in item[1])
        ]
    if not packages:
        click.echo(_("no installed adapter packages found"))
        return
    click.echo(_("installed:"))
    modules_label = _("modules:")
    for name, modules in packages:
        click.echo(f"  - {name}")
        click.echo(f"    {modules_label} {', '.join(modules)}")


def installed_adapter_package_names() -> list[str]:
    return sorted(read_project_adapter_config()["packages"])


def echo_registered_adapters(
    config_file: Path | None,
    query: str | None = None,
) -> None:
    config = read_project_adapter_config(config_file)
    current_path = current_config_path(config_file, default_adapter_config_path())
    needle = (query or "").lower()
    modules = (
        [item for item in config["modules"] if needle in item.lower()]
        if needle
        else config["modules"]
    )
    click.echo(_("registered:"))
    click.echo(_("config: {path}").format(path=current_path))
    click.echo(_("modules:"))
    for module in modules:
        click.echo(f"  - {module}")


def echo_driver_config(config_file: Path | None) -> None:
    config = read_project_driver_config(config_file)
    current_path = current_config_path(config_file, default_driver_config_path())
    click.echo(_("config: {path}").format(path=current_path))
    click.echo(_("builtin:"))
    for item in config["builtin"]:
        click.echo(f"  - {item}")


def echo_installed_drivers(query: str | None = None) -> None:
    config = read_project_driver_config()
    packages = sorted(config["packages"].items())
    if query:
        needle = query.lower()
        packages = [
            item
            for item in packages
            if needle in item[0].lower()
            or any(needle in builtin.lower() for builtin in item[1])
        ]
    if not packages:
        click.echo(_("no installed driver packages found"))
        return
    click.echo(_("installed:"))
    builtin_label = _("builtin:")
    for name, builtin in packages:
        click.echo(f"  - {name}")
        click.echo(f"    {builtin_label} {', '.join(builtin)}")


def installed_driver_package_names() -> list[str]:
    return sorted(read_project_driver_config()["packages"])


def store_module_name(item: object) -> str:
    return str(getattr(item, "module_name", "")).strip()


def store_package_dependency(
    package: object | None,
    fallback: str | None,
) -> str | None:
    if package is None:
        return fallback
    as_dependency = getattr(package, "as_dependency", None)
    if not callable(as_dependency):
        return fallback
    dependency = as_dependency()
    return dependency if isinstance(dependency, str) else fallback


def resolve_plugin_module(package: object | None, module_name: str | None) -> str:
    if module_name:
        return module_name.strip()
    resolved = store_module_name(package) if package is not None else ""
    if resolved:
        return resolved
    fail(_("plugin module name is required when package is not from store"))
    return ""


def resolve_adapter_module(package: object | None, module_name: str | None) -> str:
    if module_name:
        return module_name.strip()
    resolved = store_module_name(package) if package is not None else ""
    if resolved:
        return resolved
    fail(_("adapter module name is required when package is not from store"))
    return ""


def resolve_driver_builtin(package: object | None, builtin_name: str | None) -> str:
    if builtin_name:
        return builtin_name.strip()
    resolved = store_module_name(package) if package is not None else ""
    if resolved:
        return resolved
    fail(_("driver builtin name is required when package is not from store"))
    return ""


def install_resource_requirement(  # noqa: PLR0913
    spec: ResourceSpec,
    package_name: str | None,
    binding_value: str | None,
    requirement: str | None,
    *,
    use_store: bool,
    source_id: str,
    pip_args: tuple[str, ...],
) -> str:
    target, resolved_binding = resolve_install_request(
        spec,
        package_name,
        binding_value,
        requirement,
        use_store=use_store,
        source_id=source_id,
        fail=fail,
        store_package_dependency=store_package_dependency,
    )
    return run_install(spec, target, resolved_binding, pip_args)


def update_resource_requirement(
    spec: ResourceSpec,
    package_name: str | None,
    pip_args: tuple[str, ...],
) -> str:
    target = resolve_update_target(
        spec,
        package_name,
        prompt_package_name=prompt_package_name,
    )
    try:
        package_service.update(
            PackageOperationRequest(
                resource_kind=spec.resource_kind,
                operation="update",
                requirement=target,
                extra_args=pip_args,
            )
        )
    except StoreInstallError as exc:
        raise click.ClickException(str(exc)) from exc
    return target


def uninstall_resource_requirement(
    spec: ResourceSpec,
    package_name: str | None,
    binding_value: str | None,
    pip_args: tuple[str, ...],
) -> str:
    selected_package = package_name or prompt_package_name(
        _("choose package"),
        spec.installed_package_names(),
    )
    target = declared_package_target(selected_package)
    binding_values = resolve_uninstall_bindings(
        spec,
        selected_package,
        binding_value,
        fail=fail,
    )
    run_uninstall(spec, target, binding_values, pip_args)
    return target


PLUGIN_RESOURCE = ResourceSpec(
    module_type="plugin",
    resource_kind="plugin",
    missing_binding_message=_(
        "plugin module name is required when package is not from store"
    ),
    unbound_request_message=_("requested module is not bound to package"),
    get_bound_items=get_project_plugin_package_modules,
    installed_package_names=installed_plugin_package_names,
    select_bound_value=resolve_plugin_module,
    ensure_removable=ensure_plugin_can_be_removed,
)

ADAPTER_RESOURCE = ResourceSpec(
    module_type="adapter",
    resource_kind="adapter",
    missing_binding_message=_(
        "adapter module name is required when package is not from store"
    ),
    unbound_request_message=_("requested module is not bound to package"),
    get_bound_items=get_project_adapter_package_modules,
    installed_package_names=installed_adapter_package_names,
    select_bound_value=resolve_adapter_module,
)

DRIVER_RESOURCE = ResourceSpec(
    module_type="driver",
    resource_kind="driver",
    missing_binding_message=_(
        "driver builtin name is required when package is not from store"
    ),
    unbound_request_message=_("requested builtin is not bound to package"),
    get_bound_items=get_project_driver_package_builtin,
    installed_package_names=installed_driver_package_names,
    select_bound_value=resolve_driver_builtin,
)

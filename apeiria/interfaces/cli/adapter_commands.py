from __future__ import annotations

import click

from .i18n import _
from .store_sources import default_store_source_id
from .support import (
    ADAPTER_RESOURCE,
    add_project_adapter_module,
    config_path,
    echo_adapter_config,
    echo_installed_adapters,
    echo_registered_adapters,
    echo_store_packages_cli,
    echo_store_query,
    ensure_project_adapter_config,
    ensure_single_listing_mode,
    install_resource_requirement,
    remove_project_adapter_module,
    select_store_package_cli,
    uninstall_resource_requirement,
    update_resource_requirement,
)


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help=_("Manage Apeiria project adapters."),
)
def adapter() -> None:
    """Manage Apeiria project adapters."""


@adapter.command(
    "store",
    help=_("Browse nonebot adapter store with interactive selection."),
)
@click.argument("query", required=False)
@click.option(
    "--source",
    "source_id",
    default=default_store_source_id(),
    show_default=True,
    help=_("Choose which store source to use."),
)
def adapter_store(query: str | None, source_id: str) -> None:
    item = select_store_package_cli("adapter", query, source_id)
    echo_store_packages_cli([item], source_id)


@adapter.command(
    "init",
    help=_("Create apeiria.adapters.toml if it does not exist."),
    hidden=True,
)
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
def adapter_init(config_arg: str | None) -> None:
    target = ensure_project_adapter_config(config_path(config_arg))
    click.echo(_("initialized: {target}").format(target=target))


@adapter.command(
    "list", help=_("List registered adapters or installed adapter packages.")
)
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
@click.option("--installed", is_flag=True, help=_("List installed adapter packages."))
@click.option(
    "--registered", is_flag=True, help=_("List registered adapter config only.")
)
@click.option(
    "--store", "use_store", is_flag=True, help=_("List official store packages.")
)
def adapter_list(
    config_arg: str | None,
    *,
    installed: bool,
    registered: bool,
    use_store: bool,
) -> None:
    ensure_single_listing_mode(
        installed=installed,
        registered=registered,
        use_store=use_store,
    )
    if installed:
        echo_installed_adapters()
        return
    if registered:
        echo_registered_adapters(config_path(config_arg))
        return
    if use_store:
        echo_store_query("adapter", source_id=default_store_source_id())
        return
    echo_registered_adapters(config_path(config_arg))
    click.echo()
    echo_installed_adapters()


@adapter.command(
    "search",
    help=_("Search registered adapters or installed adapter packages."),
    hidden=True,
)
@click.argument("query", required=False)
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
@click.option("--installed", is_flag=True, help=_("Search installed adapter packages."))
@click.option(
    "--registered", is_flag=True, help=_("Search registered adapter config only.")
)
@click.option(
    "--store", "use_store", is_flag=True, help=_("Search official store packages.")
)
@click.option(
    "--source",
    "source_id",
    default=default_store_source_id(),
    show_default=True,
    help=_("Choose which store source to use."),
)
def adapter_search(  # noqa: PLR0913
    query: str | None,
    config_arg: str | None,
    *,
    installed: bool,
    registered: bool,
    use_store: bool,
    source_id: str,
) -> None:
    ensure_single_listing_mode(
        installed=installed,
        registered=registered,
        use_store=use_store,
    )
    if installed:
        echo_installed_adapters(query)
        return
    if registered:
        echo_registered_adapters(config_path(config_arg), query)
        return
    if use_store:
        echo_store_query("adapter", query=query, source_id=source_id)
        return
    echo_registered_adapters(config_path(config_arg), query)
    click.echo()
    echo_installed_adapters(query)


@adapter.command(
    "register",
    help=_("Register an adapter module in apeiria.adapters.toml."),
    hidden=True,
)
@click.argument("module_name")
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
def adapter_register(module_name: str, config_arg: str | None) -> None:
    config_file = config_path(config_arg)
    ensure_project_adapter_config(config_file)
    add_project_adapter_module(module_name, config_file)
    click.echo(_("registered module: {module}").format(module=module_name))
    echo_adapter_config(config_file)


@adapter.command(
    "unregister",
    help=_("Remove an adapter module from apeiria.adapters.toml."),
    hidden=True,
)
@click.argument("module_name")
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
def adapter_unregister(module_name: str, config_arg: str | None) -> None:
    config_file = config_path(config_arg)
    ensure_project_adapter_config(config_file)
    remove_project_adapter_module(module_name, config_file)
    click.echo(_("unregistered module: {module}").format(module=module_name))
    echo_adapter_config(config_file)


@adapter.command(
    "install",
    context_settings={"ignore_unknown_options": True},
    help=_("Install an adapter package."),
)
@click.argument("package_name", required=False)
@click.argument("pip_args", nargs=-1)
@click.option(
    "--store", "use_store", is_flag=True, help=_("Choose from official store.")
)
@click.option(
    "--module",
    "module_name",
    help=_("Adapter module name to register when store metadata is unavailable."),
)
@click.option(
    "--source",
    "source_id",
    default=default_store_source_id(),
    show_default=True,
    help=_("Choose which store source to use."),
)
@click.option(
    "--requirement",
    "requirement",
    help=_("Install from a raw requirement string such as a git URL or local path."),
)
def adapter_install(  # noqa: PLR0913
    package_name: str | None,
    pip_args: tuple[str, ...],
    *,
    use_store: bool,
    module_name: str | None,
    source_id: str,
    requirement: str | None,
) -> None:
    installed_requirement = install_resource_requirement(
        ADAPTER_RESOURCE,
        package_name,
        module_name,
        requirement,
        pip_args=pip_args,
        use_store=use_store,
        source_id=source_id,
    )
    click.echo(_("installed package: {package}").format(package=installed_requirement))


@adapter.command("add", context_settings={"ignore_unknown_options": True}, hidden=True)
@click.argument("package_name", required=False)
@click.argument("pip_args", nargs=-1)
@click.option(
    "--store", "use_store", is_flag=True, help=_("Choose from official store.")
)
@click.option(
    "--module",
    "module_name",
    help=_("Adapter module name to register when store metadata is unavailable."),
)
@click.option(
    "--source",
    "source_id",
    default=default_store_source_id(),
    hidden=True,
)
@click.option(
    "--requirement",
    "requirement",
    help=_("Install from a raw requirement string such as a git URL or local path."),
)
def adapter_add(  # noqa: PLR0913
    package_name: str | None,
    pip_args: tuple[str, ...],
    *,
    use_store: bool,
    module_name: str | None,
    source_id: str,
    requirement: str | None,
) -> None:
    assert adapter_install.callback is not None
    adapter_install.callback(
        package_name,
        pip_args,
        use_store=use_store,
        module_name=module_name,
        source_id=source_id,
        requirement=requirement,
    )


@adapter.command(
    "update",
    context_settings={"ignore_unknown_options": True},
    help=_("Update an adapter package with current environment manager."),
)
@click.argument("package_name", required=False)
@click.argument("pip_args", nargs=-1)
def adapter_update(package_name: str | None, pip_args: tuple[str, ...]) -> None:
    target = update_resource_requirement(
        ADAPTER_RESOURCE,
        package_name,
        pip_args,
    )
    click.echo(_("updated package: {package}").format(package=target))


@adapter.command(
    "uninstall",
    context_settings={"ignore_unknown_options": True},
    help=_("Uninstall an adapter package."),
)
@click.argument("package_name", required=False)
@click.argument("pip_args", nargs=-1)
@click.option(
    "--module",
    "module_name",
    help=_("Adapter module name to unregister when package metadata is unavailable."),
)
def adapter_uninstall(
    package_name: str | None,
    pip_args: tuple[str, ...],
    module_name: str | None,
) -> None:
    target = uninstall_resource_requirement(
        ADAPTER_RESOURCE,
        package_name,
        module_name,
        pip_args,
    )
    click.echo(_("uninstalled package: {package}").format(package=target))


@adapter.command(
    "remove",
    context_settings={"ignore_unknown_options": True},
    hidden=True,
)
@click.argument("package_name", required=False)
@click.argument("pip_args", nargs=-1)
@click.option(
    "--module",
    "module_name",
    help=_("Adapter module name to unregister when package metadata is unavailable."),
)
def adapter_remove(
    package_name: str | None,
    pip_args: tuple[str, ...],
    module_name: str | None,
) -> None:
    assert adapter_uninstall.callback is not None
    adapter_uninstall.callback(package_name, pip_args, module_name)

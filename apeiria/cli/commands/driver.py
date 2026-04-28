from __future__ import annotations

import click

from apeiria.cli.i18n import _
from apeiria.cli.output import echo_json
from apeiria.cli.store_sources import default_store_source_id
from apeiria.cli.support import (
    DRIVER_RESOURCE,
    add_project_driver_builtin,
    config_path,
    default_driver_config_path,
    driver_registered_payload,
    echo_driver_config,
    echo_installed_drivers,
    echo_store_packages_cli,
    echo_store_query,
    ensure_project_driver_config,
    ensure_single_listing_mode,
    get_project_driver_kwargs,
    install_resource_requirement,
    installed_drivers_payload,
    read_project_driver_config,
    remove_project_driver_builtin,
    select_store_package_cli,
    store_packages_cli,
    store_packages_payload,
    uninstall_resource_requirement,
    update_resource_requirement,
)


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help=_("Manage Apeiria project drivers."),
)
def driver() -> None:
    """Manage Apeiria project drivers."""


@driver.command(
    "store",
    help=_("Browse nonebot driver store with interactive selection."),
)
@click.argument("query", required=False)
@click.option(
    "--source",
    "source_id",
    default=default_store_source_id(),
    show_default=True,
    help=_("Choose which store source to use."),
)
def driver_store(query: str | None, source_id: str) -> None:
    item = select_store_package_cli("driver", query, source_id)
    echo_store_packages_cli([item], source_id)


@driver.command(
    "init",
    help=_("Create apeiria.drivers.toml if it does not exist."),
    hidden=True,
)
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
def driver_init(config_arg: str | None) -> None:
    target = ensure_project_driver_config(config_path(config_arg))
    click.echo(_("initialized: {target}").format(target=target))


@driver.command("list", help=_("List registered drivers or installed driver packages."))
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
@click.option("--installed", is_flag=True, help=_("List installed driver packages."))
@click.option(
    "--registered", is_flag=True, help=_("List registered driver config only.")
)
@click.option(
    "--store", "use_store", is_flag=True, help=_("List official store packages.")
)
@click.option("--json", "json_output", is_flag=True, help=_("Emit JSON output."))
def driver_list(
    config_arg: str | None,
    *,
    installed: bool,
    registered: bool,
    use_store: bool,
    json_output: bool,
) -> None:
    ensure_single_listing_mode(
        installed=installed,
        registered=registered,
        use_store=use_store,
    )
    if json_output:
        echo_json(
            _driver_list_payload(
                config_arg,
                installed=installed,
                registered=registered,
                use_store=use_store,
            )
        )
        return
    if installed:
        echo_installed_drivers()
        return
    if registered:
        echo_driver_config(config_path(config_arg))
        return
    if use_store:
        echo_store_query("driver", source_id=default_store_source_id())
        return
    echo_driver_config(config_path(config_arg))
    click.echo()
    echo_installed_drivers()


@driver.command(
    "search",
    help=_("Search registered drivers or installed driver packages."),
)
@click.argument("query", required=False)
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
@click.option("--installed", is_flag=True, help=_("Search installed driver packages."))
@click.option(
    "--registered", is_flag=True, help=_("Search registered driver config only.")
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
@click.option("--json", "json_output", is_flag=True, help=_("Emit JSON output."))
def driver_search(  # noqa: PLR0913
    query: str | None,
    config_arg: str | None,
    *,
    installed: bool,
    registered: bool,
    use_store: bool,
    source_id: str,
    json_output: bool,
) -> None:
    ensure_single_listing_mode(
        installed=installed,
        registered=registered,
        use_store=use_store,
    )
    if json_output:
        echo_json(
            _driver_search_payload(
                query,
                config_arg,
                source_id=source_id,
                modes=(installed, registered, use_store),
            )
        )
        return
    if installed:
        echo_installed_drivers(query)
        return
    if use_store:
        echo_store_query("driver", query=query, source_id=source_id)
        return
    config_file = config_path(config_arg)
    config = read_project_driver_config(config_file)
    needle = (query or "").lower()
    filtered_builtin = (
        [item for item in config["builtin"] if needle in item.lower()]
        if needle
        else config["builtin"]
    )
    current_path = default_driver_config_path() if config_file is None else config_file
    click.echo(_("config: {path}").format(path=current_path))
    click.echo(_("builtin:"))
    for item in filtered_builtin:
        click.echo(f"  - {item}")
    if not registered:
        click.echo()
        echo_installed_drivers(query)


def _driver_list_payload(
    config_arg: str | None,
    *,
    installed: bool,
    registered: bool,
    use_store: bool,
) -> dict[str, object]:
    if installed:
        return installed_drivers_payload()
    if registered:
        return driver_registered_payload(config_path(config_arg))
    if use_store:
        source_id = default_store_source_id()
        return store_packages_payload(
            "driver",
            store_packages_cli("driver", source_id=source_id),
            source_id,
        )
    return {
        "resource": "driver",
        "mode": "combined",
        "registered": driver_registered_payload(config_path(config_arg)),
        "installed": installed_drivers_payload(),
    }


def _driver_search_payload(
    query: str | None,
    config_arg: str | None,
    *,
    source_id: str,
    modes: tuple[bool, bool, bool],
) -> dict[str, object]:
    installed, registered, use_store = modes
    if installed:
        return installed_drivers_payload(query)
    if registered:
        return driver_registered_payload(config_path(config_arg), query)
    if use_store:
        return store_packages_payload(
            "driver",
            store_packages_cli("driver", query=query, source_id=source_id),
            source_id,
        )
    return {
        "resource": "driver",
        "mode": "combined",
        "registered": driver_registered_payload(config_path(config_arg), query),
        "installed": installed_drivers_payload(query),
    }


@driver.command(
    "install",
    context_settings={"ignore_unknown_options": True},
    help=_("Install a driver package."),
)
@click.argument("package_name", required=False)
@click.argument("pip_args", nargs=-1)
@click.option(
    "--store", "use_store", is_flag=True, help=_("Choose from official store.")
)
@click.option(
    "--builtin",
    "builtin_name",
    help=_("Driver builtin name to register when store metadata is unavailable."),
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
def driver_install(  # noqa: PLR0913
    package_name: str | None,
    pip_args: tuple[str, ...],
    *,
    use_store: bool,
    builtin_name: str | None,
    source_id: str,
    requirement: str | None,
) -> None:
    installed_requirement = install_resource_requirement(
        DRIVER_RESOURCE,
        package_name,
        builtin_name,
        requirement,
        pip_args=pip_args,
        use_store=use_store,
        source_id=source_id,
    )
    click.echo(_("installed package: {package}").format(package=installed_requirement))


@driver.command("add", context_settings={"ignore_unknown_options": True}, hidden=True)
@click.argument("package_name", required=False)
@click.argument("pip_args", nargs=-1)
@click.option(
    "--store", "use_store", is_flag=True, help=_("Choose from official store.")
)
@click.option(
    "--builtin",
    "builtin_name",
    help=_("Driver builtin name to register when store metadata is unavailable."),
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
def driver_add(  # noqa: PLR0913
    package_name: str | None,
    pip_args: tuple[str, ...],
    *,
    use_store: bool,
    builtin_name: str | None,
    source_id: str,
    requirement: str | None,
) -> None:
    assert driver_install.callback is not None
    driver_install.callback(
        package_name,
        pip_args,
        use_store=use_store,
        builtin_name=builtin_name,
        source_id=source_id,
        requirement=requirement,
    )


@driver.command(
    "update",
    context_settings={"ignore_unknown_options": True},
    help=_("Update a driver package with current environment manager."),
)
@click.argument("package_name", required=False)
@click.argument("pip_args", nargs=-1)
def driver_update(package_name: str | None, pip_args: tuple[str, ...]) -> None:
    target = update_resource_requirement(
        DRIVER_RESOURCE,
        package_name,
        pip_args,
    )
    click.echo(_("updated package: {package}").format(package=target))


@driver.command(
    "uninstall",
    context_settings={"ignore_unknown_options": True},
    help=_("Uninstall a driver package."),
)
@click.argument("package_name", required=False)
@click.argument("pip_args", nargs=-1)
@click.option(
    "--builtin",
    "builtin_name",
    help=_("Driver builtin name to unregister when package metadata is unavailable."),
)
def driver_uninstall(
    package_name: str | None,
    pip_args: tuple[str, ...],
    builtin_name: str | None,
) -> None:
    target = uninstall_resource_requirement(
        DRIVER_RESOURCE,
        package_name,
        builtin_name,
        pip_args,
    )
    click.echo(_("uninstalled package: {package}").format(package=target))


@driver.command(
    "remove",
    context_settings={"ignore_unknown_options": True},
    hidden=True,
)
@click.argument("package_name", required=False)
@click.argument("pip_args", nargs=-1)
@click.option(
    "--builtin",
    "builtin_name",
    help=_("Driver builtin name to unregister when package metadata is unavailable."),
)
def driver_remove(
    package_name: str | None,
    pip_args: tuple[str, ...],
    builtin_name: str | None,
) -> None:
    assert driver_uninstall.callback is not None
    driver_uninstall.callback(package_name, pip_args, builtin_name)


@driver.command(
    "register",
    help=_("Register a built-in driver entry in apeiria.drivers.toml."),
    hidden=True,
)
@click.argument("builtin_name")
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
def driver_register(builtin_name: str, config_arg: str | None) -> None:
    config_file = config_path(config_arg)
    ensure_project_driver_config(config_file)
    add_project_driver_builtin(builtin_name, config_file)
    click.echo(_("registered builtin: {builtin}").format(builtin=builtin_name))
    echo_driver_config(config_file)


@driver.command(
    "unregister",
    help=_("Remove a built-in driver entry from apeiria.drivers.toml."),
    hidden=True,
)
@click.argument("builtin_name")
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
def driver_unregister(builtin_name: str, config_arg: str | None) -> None:
    config_file = config_path(config_arg)
    ensure_project_driver_config(config_file)
    remove_project_driver_builtin(builtin_name, config_file)
    click.echo(_("unregistered builtin: {builtin}").format(builtin=builtin_name))
    echo_driver_config(config_file)


@driver.command(
    "show",
    help=_("Show effective NoneBot init kwargs generated from apeiria.drivers.toml."),
)
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
def driver_show(config_arg: str | None) -> None:
    kwargs = get_project_driver_kwargs(config_path(config_arg))
    if not kwargs:
        click.echo("{}")
        return
    for key, value in kwargs.items():
        click.echo(f"{key}={value}")

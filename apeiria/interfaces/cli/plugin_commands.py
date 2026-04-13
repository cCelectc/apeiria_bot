from __future__ import annotations

import click

from apeiria.infra.runtime.bootstrap import initialize_nonebot
from apeiria.infra.runtime.environment import ensure_plugin_project

from .i18n import _
from .store_sources import default_store_source_id
from .support import (
    PLUGIN_RESOURCE,
    add_project_plugin_dir,
    add_project_plugin_module,
    config_path,
    echo_installed_plugins,
    echo_plugin_config,
    echo_registered_plugins,
    echo_store_packages_cli,
    echo_store_query,
    ensure_plugin_can_be_removed,
    ensure_project_plugin_config,
    ensure_single_listing_mode,
    install_resource_requirement,
    remove_project_plugin_dir,
    remove_project_plugin_module,
    select_store_package_cli,
    uninstall_resource_requirement,
    update_resource_requirement,
)


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help=_("Manage Apeiria project plugins."),
)
def plugin() -> None:
    """Manage Apeiria project plugins."""


@plugin.command(
    "store",
    help=_("Browse nonebot plugin store with interactive selection."),
)
@click.argument("query", required=False)
@click.option(
    "--source",
    "source_id",
    default=default_store_source_id(),
    show_default=True,
    help=_("Choose which store source to use."),
)
def plugin_store(query: str | None, source_id: str) -> None:
    item = select_store_package_cli("plugin", query, source_id)
    echo_store_packages_cli([item], source_id)


@plugin.command(
    "init",
    help=_("Create apeiria.plugins.toml and the user plugin project if missing."),
    hidden=True,
)
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
def plugin_init(config_arg: str | None) -> None:
    target = ensure_project_plugin_config(config_path(config_arg))
    plugin_root = ensure_plugin_project()
    click.echo(_("initialized: {target}").format(target=target))
    click.echo(_("initialized: {target}").format(target=plugin_root))


@plugin.command("list", help=_("List registered plugins or installed plugin packages."))
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
@click.option("--installed", is_flag=True, help=_("List installed plugin packages."))
@click.option(
    "--registered", is_flag=True, help=_("List registered plugin config only.")
)
@click.option(
    "--store", "use_store", is_flag=True, help=_("List official store packages.")
)
def plugin_list(
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
        echo_installed_plugins()
        return
    if registered:
        echo_registered_plugins(config_path(config_arg))
        return
    if use_store:
        echo_store_query("plugin", source_id=default_store_source_id())
        return
    echo_registered_plugins(config_path(config_arg))
    click.echo()
    echo_installed_plugins()


@plugin.command(
    "search",
    help=_("Search registered plugins or installed plugin packages."),
    hidden=True,
)
@click.argument("query", required=False)
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
@click.option("--installed", is_flag=True, help=_("Search installed plugin packages."))
@click.option(
    "--registered", is_flag=True, help=_("Search registered plugin config only.")
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
def plugin_search(  # noqa: PLR0913
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
        echo_installed_plugins(query)
        return
    if registered:
        echo_registered_plugins(config_path(config_arg), query)
        return
    if use_store:
        echo_store_query("plugin", query=query, source_id=source_id)
        return
    echo_registered_plugins(config_path(config_arg), query)
    click.echo()
    echo_installed_plugins(query)


@plugin.command(
    "register",
    help=_("Register a plugin module in apeiria.plugins.toml."),
    hidden=True,
)
@click.argument("module_name")
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
def plugin_register(module_name: str, config_arg: str | None) -> None:
    config_file = config_path(config_arg)
    ensure_project_plugin_config(config_file)
    add_project_plugin_module(module_name, config_file)
    click.echo(_("registered module: {module}").format(module=module_name))
    echo_plugin_config(config_file)


@plugin.command(
    "unregister",
    help=_("Remove a plugin module from apeiria.plugins.toml."),
    hidden=True,
)
@click.argument("module_name")
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
def plugin_unregister(module_name: str, config_arg: str | None) -> None:
    ensure_plugin_can_be_removed(module_name)
    config_file = config_path(config_arg)
    ensure_project_plugin_config(config_file)
    remove_project_plugin_module(module_name, config_file)
    click.echo(_("unregistered module: {module}").format(module=module_name))
    echo_plugin_config(config_file)


@plugin.command(
    "install",
    context_settings={"ignore_unknown_options": True},
    help=_("Install a plugin package."),
)
@click.argument("package_name", required=False)
@click.argument("pip_args", nargs=-1)
@click.option(
    "--store", "use_store", is_flag=True, help=_("Choose from official store.")
)
@click.option(
    "--module",
    "module_name",
    help=_("Plugin module name to register when store metadata is unavailable."),
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
def plugin_install(  # noqa: PLR0913
    package_name: str | None,
    pip_args: tuple[str, ...],
    *,
    use_store: bool,
    module_name: str | None,
    source_id: str,
    requirement: str | None,
) -> None:
    installed_requirement = install_resource_requirement(
        PLUGIN_RESOURCE,
        package_name,
        module_name,
        requirement,
        pip_args=pip_args,
        use_store=use_store,
        source_id=source_id,
    )
    click.echo(_("installed package: {package}").format(package=installed_requirement))


@plugin.command("add", context_settings={"ignore_unknown_options": True}, hidden=True)
@click.argument("package_name", required=False)
@click.argument("pip_args", nargs=-1)
@click.option(
    "--store", "use_store", is_flag=True, help=_("Choose from official store.")
)
@click.option(
    "--module",
    "module_name",
    help=_("Plugin module name to register when store metadata is unavailable."),
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
def plugin_add(  # noqa: PLR0913
    package_name: str | None,
    pip_args: tuple[str, ...],
    *,
    use_store: bool,
    module_name: str | None,
    source_id: str,
    requirement: str | None,
) -> None:
    assert plugin_install.callback is not None
    plugin_install.callback(
        package_name,
        pip_args,
        use_store=use_store,
        module_name=module_name,
        source_id=source_id,
        requirement=requirement,
    )


@plugin.command(
    "update",
    context_settings={"ignore_unknown_options": True},
    help=_("Update a plugin package with current environment manager."),
)
@click.argument("package_name", required=False)
@click.argument("pip_args", nargs=-1)
def plugin_update(package_name: str | None, pip_args: tuple[str, ...]) -> None:
    target = update_resource_requirement(
        PLUGIN_RESOURCE,
        package_name,
        pip_args,
    )
    click.echo(_("updated package: {package}").format(package=target))


@plugin.command(
    "uninstall",
    context_settings={"ignore_unknown_options": True},
    help=_("Uninstall a plugin package."),
)
@click.argument("package_name", required=False)
@click.argument("pip_args", nargs=-1)
@click.option(
    "--module",
    "module_name",
    help=_("Plugin module name to unregister when package metadata is unavailable."),
)
def plugin_uninstall(
    package_name: str | None,
    pip_args: tuple[str, ...],
    module_name: str | None,
) -> None:
    target = uninstall_resource_requirement(
        PLUGIN_RESOURCE,
        package_name,
        module_name,
        pip_args,
    )
    click.echo(_("uninstalled package: {package}").format(package=target))


@plugin.command(
    "remove",
    context_settings={"ignore_unknown_options": True},
    hidden=True,
)
@click.argument("package_name", required=False)
@click.argument("pip_args", nargs=-1)
@click.option(
    "--module",
    "module_name",
    help=_("Plugin module name to unregister when package metadata is unavailable."),
)
def plugin_remove(
    package_name: str | None,
    pip_args: tuple[str, ...],
    module_name: str | None,
) -> None:
    assert plugin_uninstall.callback is not None
    plugin_uninstall.callback(package_name, pip_args, module_name)


@plugin.command(
    "diagnose",
    help=_("Show plugin registration diagnostics."),
)
def plugin_diagnose() -> None:
    try:
        initialize_nonebot()
    except Exception as exc:
        raise click.ClickException(
            _("plugin diagnose failed: {error}").format(error=str(exc))
        ) from exc

    from apeiria.app.plugins.registration_service import (
        plugin_registration_config_service,
    )

    state = plugin_registration_config_service.get_plugin_config()
    module_items = state.modules
    dir_items = state.dirs

    click.echo(_("registered plugin diagnostics:"))
    if not module_items:
        click.echo(_("no registered plugin modules"))
    else:
        for item in module_items:
            loaded = _("loaded") if item.is_loaded else _("not loaded")
            importable = _("importable") if item.is_importable else _("not importable")
            click.echo(f"  - {item.name} ({loaded}, {importable})")

    if dir_items:
        click.echo(_("registered plugin dirs:"))
        for item in dir_items:
            exists = _("exists") if item.exists else _("missing")
            loaded = _("loaded") if item.is_loaded else _("not loaded")
            click.echo(f"  - {item.path} ({exists}, {loaded})")

    not_importable_modules = [item for item in module_items if not item.is_importable]
    not_loaded_modules = [item for item in module_items if not item.is_loaded]
    missing_dirs = [item for item in dir_items if not item.exists]
    not_loaded_dirs = [item for item in dir_items if item.exists and not item.is_loaded]

    click.echo()
    click.echo(_("plugin diagnose summary:"))
    click.echo(_("module total: {count}").format(count=len(module_items)))
    click.echo(
        _("module not importable: {count}").format(count=len(not_importable_modules))
    )
    click.echo(_("module not loaded: {count}").format(count=len(not_loaded_modules)))
    click.echo(_("dir total: {count}").format(count=len(dir_items)))
    click.echo(_("dir missing: {count}").format(count=len(missing_dirs)))
    click.echo(_("dir not loaded: {count}").format(count=len(not_loaded_dirs)))


@plugin.command(
    "add-dir",
    help=_("Register a plugin directory in apeiria.plugins.toml."),
    hidden=True,
)
@click.argument("directory")
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
def plugin_add_dir(directory: str, config_arg: str | None) -> None:
    config_file = config_path(config_arg)
    ensure_project_plugin_config(config_file)
    add_project_plugin_dir(directory, config_file)
    click.echo(_("added dir: {directory}").format(directory=directory))
    echo_plugin_config(config_file)


@plugin.command(
    "remove-dir",
    help=_("Remove a plugin directory from apeiria.plugins.toml."),
    hidden=True,
)
@click.argument("directory")
@click.option("--config", "config_arg", type=click.Path(dir_okay=False))
def plugin_remove_dir(directory: str, config_arg: str | None) -> None:
    config_file = config_path(config_arg)
    ensure_project_plugin_config(config_file)
    remove_project_plugin_dir(directory, config_file)
    click.echo(_("removed dir: {directory}").format(directory=directory))
    echo_plugin_config(config_file)

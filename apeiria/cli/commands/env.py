from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from apeiria.cli.i18n import _
from apeiria.environment import environment_service, health_service

if TYPE_CHECKING:
    from apeiria.environment.models import ProjectConfigBootstrapResult


def project_root() -> Path:
    return environment_service.project_root


def main_config_path(root: Path | None = None) -> Path:
    del root
    return environment_service.main_config_path()


def initialize_user_environment(
    *,
    no_dev: bool = False,
) -> "ProjectConfigBootstrapResult":
    return environment_service.initialize_user_environment(no_dev=no_dev)


def repair_user_environment() -> None:
    environment_service.repair_user_environment()


def validate_database_schema() -> None:
    environment_service.validate_database_schema()


def repair_database_schema() -> None:
    try:
        environment_service.repair_database_schema()
    except Exception as exc:
        hint = _startup_check_hint(str(exc))
        if hint:
            raise click.ClickException(
                _("database repair failed: {error}\nnext step: {hint}").format(
                    error=str(exc),
                    hint=hint,
                )
            ) from exc
        raise click.ClickException(
            _("database repair failed: {error}").format(error=str(exc))
        ) from exc


def raise_click_runtime_error(exc: RuntimeError) -> None:
    raise click.ClickException(str(exc)) from exc


def check_system_dependencies() -> None:
    snapshot = environment_service.get_environment_snapshot()
    if not snapshot.uv_available:
        raise click.ClickException(
            _("missing system dependencies: {deps}").format(deps="uv")
        )

    frontend_missing: list[str] = []
    needs_frontend_toolchain = (
        snapshot.frontend_workspace_exists and not snapshot.frontend_dist_exists
    )
    if needs_frontend_toolchain:
        if not snapshot.node_available:
            frontend_missing.append("node")
        if not snapshot.pnpm_available and not snapshot.npm_available:
            frontend_missing.append("pnpm-or-npm")
    if frontend_missing:
        click.echo(
            _("frontend toolchain missing: {deps}").format(
                deps=", ".join(frontend_missing)
            ),
            err=True,
        )


def build_frontend() -> None:
    try:
        environment_service.build_frontend_sync()
    except RuntimeError as exc:
        detail = str(exc)
        if detail == "build_tool_unavailable":
            raise click.ClickException(
                _("frontend toolchain missing: {deps}").format(deps="pnpm-or-npm")
            ) from exc
        raise click.ClickException(detail) from exc


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help=_("Inspect and migrate Apeiria environments."),
)
def env() -> None:
    """Inspect and migrate Apeiria environments."""


@env.command("init", help=_("Initialize Apeiria user environment with uv."))
@click.option(
    "--no-dev",
    is_flag=True,
    help=_("Sync the main project environment without development dependencies."),
)
def env_init(*, no_dev: bool) -> None:
    check_system_dependencies()
    try:
        result = initialize_user_environment(no_dev=no_dev)
    except RuntimeError as exc:
        raise_click_runtime_error(exc)
    for filename in result.created:
        click.echo(_("created config: {filename}").format(filename=filename))
    for filename in result.skipped:
        click.echo(_("skipped config: {filename}").format(filename=filename))
    click.echo(_("initialized environment"))
    click.echo(
        _(
            "hint: if you need local startup customization, see user_bot.example.py"
        )
    )


@env.command("repair", help=_("Repair Apeiria user environment with uv."))
def env_repair() -> None:
    check_system_dependencies()
    try:
        repair_user_environment()
        repair_database_schema()
    except RuntimeError as exc:
        raise_click_runtime_error(exc)
    click.echo(_("repaired environment"))


@click.command(help=_("Initialize Apeiria user environment with uv."), hidden=True)
@click.option(
    "--no-dev",
    is_flag=True,
    help=_("Sync the main project environment without development dependencies."),
)
def init(*, no_dev: bool) -> None:
    assert env_init.callback is not None
    env_init.callback(no_dev=no_dev)


@click.command(help=_("Repair Apeiria user environment with uv."), hidden=True)
def repair() -> None:
    assert env_repair.callback is not None
    env_repair.callback()


@click.command(help=_("Run bot.py with the current project Python environment."))
@click.option(
    "--build",
    "build_frontend_first",
    is_flag=True,
    help=_("Build Web UI frontend assets before running the bot."),
)
@click.argument("extra_args", nargs=-1)
def run(*, build_frontend_first: bool, extra_args: tuple[str, ...]) -> None:
    if build_frontend_first:
        build_frontend()
    result = subprocess.run(
        [sys.executable, "bot.py", *extra_args],
        cwd=project_root(),
        check=False,
    )
    if result.returncode != 0:
        raise click.exceptions.Exit(result.returncode)


@env.command("info", help=_("Show current Apeiria environment paths and status."))
def env_info() -> None:
    snapshot = environment_service.get_environment_snapshot()
    lines = [
        f"project_root={snapshot.project_root}",
        f"uv_available={snapshot.uv_available}",
        f"node_available={snapshot.node_available}",
        f"pnpm_available={snapshot.pnpm_available}",
        f"npm_available={snapshot.npm_available}",
        f"main_lock_exists={snapshot.main_lock_exists}",
        f"plugin_project={snapshot.plugin_project_root}",
        f"plugin_project_exists={snapshot.plugin_project_exists}",
        f"plugin_lock_exists={snapshot.plugin_lock_exists}",
        f"main_config_path={snapshot.main_config_path}",
        f"project_config_exists={snapshot.project_config_exists}",
        f"plugin_config_exists={snapshot.plugin_config_exists}",
        f"adapter_config_exists={snapshot.adapter_config_exists}",
        f"driver_config_exists={snapshot.driver_config_exists}",
    ]
    for line in lines:
        click.echo(line)


def _echo_system_health(*, include_checks: bool) -> None:
    snapshot = health_service.get_snapshot()
    click.echo(f"status={snapshot.status}")
    click.echo(f"project_root={snapshot.project_root}")
    if include_checks:
        failed_checks = [check for check in snapshot.checks if not check.ok]
        if not failed_checks:
            click.echo("checks=ok (0 issues)")
            return

        click.echo(f"checks=warning ({len(failed_checks)} issues)")
        for check in failed_checks:
            click.echo(f"- {check.key}: {check.message}")
            if check.hint:
                click.echo(f"  hint: {check.hint}")


def _startup_check_hint(error_text: str) -> str | None:
    normalized = error_text.lower()
    config_files = (
        "apeiria.config.toml",
        "apeiria.plugins.toml",
        "apeiria.adapters.toml",
        "apeiria.drivers.toml",
    )
    if "no such file" in normalized and any(
        file_name in normalized for file_name in config_files
    ):
        return _(
            "run `apeiria env init`"
        )

    rules: tuple[tuple[str, str], ...] = (
        (
            "failed to bootstrap plugin config",
            "check plugin config conflicts in project plugins and rerun check",
        ),
        (
            "partially initialized apeiria database tables",
            "run `apeiria env repair` after backing up or fixing the database state",
        ),
        (
            "schema metadata is missing a valid schema version",
            "run `apeiria env repair` to reconcile Apeiria database metadata",
        ),
        (
            "database schema version is newer than this apeiria build",
            "use a matching Apeiria version or restore a compatible database backup",
        ),
        (
            "no schema migration path is available",
            "upgrade with a compatible Apeiria release or add the required migration",
        ),
        (
            "web_ui auth storage is corrupted",
            ("fix or restore `data/web_ui/secret.json`, then rerun check"),
        ),
    )
    for pattern, hint in rules:
        if pattern in normalized:
            return _(hint)
    return None


@env.command("doctor", help=_("Run non-mutating environment health checks."))
def env_doctor() -> None:
    _echo_system_health(include_checks=True)


@click.command(help=_("Show Apeiria system health summary."))
def status() -> None:
    _echo_system_health(include_checks=True)


@click.command(help=_("Validate bot startup without entering the event loop."))
def check() -> None:
    try:
        validate_database_schema()
    except Exception as exc:
        hint = _startup_check_hint(str(exc))
        if hint:
            raise click.ClickException(
                _("startup check failed: {error}\nnext step: {hint}").format(
                    error=str(exc), hint=hint
                )
            ) from exc
        raise click.ClickException(
            _("startup check failed: {error}").format(error=str(exc))
        ) from exc
    click.echo(_("startup check passed"))


@env.command("export", help=_("Export local runtime state for migration."))
@click.argument("output_dir", required=False)
def env_export(output_dir: str | None) -> None:
    target_root, copied = environment_service.export_runtime_state(
        Path(output_dir) if output_dir else None
    )
    click.echo(_("exported files: {count}").format(count=copied))
    click.echo(_("export target: {target}").format(target=target_root))


@env.command("import", help=_("Import local runtime state from a migration bundle."))
@click.argument("input_dir")
def env_import(input_dir: str) -> None:
    try:
        _target_root, copied = environment_service.import_runtime_state(Path(input_dir))
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(_("imported files: {count}").format(count=copied))

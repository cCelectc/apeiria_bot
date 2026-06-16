from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from apeiria.cli.context import active_environment_service, active_health_service
from apeiria.cli.i18n import _
from apeiria.cli.output import echo_json
from apeiria.utils.project_context import runtime_project_root_env_var

if TYPE_CHECKING:
    from apeiria.environment.models import ProjectConfigBootstrapResult


def project_root() -> Path:
    return active_environment_service().project_root


def main_config_path(root: Path | None = None) -> Path:
    if root is not None:
        return root / "apeiria.config.toml"
    return active_environment_service().main_config_path()


def initialize_user_environment(
    *,
    no_dev: bool = False,
) -> "ProjectConfigBootstrapResult":
    return active_environment_service().initialize_user_environment(no_dev=no_dev)


def repair_user_environment() -> None:
    active_environment_service().repair_user_environment()


def validate_database_schema() -> None:
    active_environment_service().validate_database_schema()


def repair_database_schema() -> None:
    try:
        active_environment_service().repair_database_schema()
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
    snapshot = active_environment_service().get_environment_snapshot()
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
    import json

    service = active_environment_service()
    status = service.get_frontend_build_status()
    if not status.can_build or status.build_tool is None:
        raise click.ClickException(
            _("frontend toolchain missing: {deps}").format(deps="pnpm-or-npm")
        )

    async def _stream() -> None:
        failed = False
        async for line_bytes in service.stream_frontend_rebuild():
            try:
                event = json.loads(line_bytes.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if event.get("event") == "chunk":
                click.echo(event.get("chunk", ""), nl=False, err=True)
            elif event.get("event") == "error":
                click.echo(event.get("detail", "build_failed"), err=True)
                failed = True
            elif event.get("event") == "done":
                pass
        if failed:
            raise click.ClickException(_("frontend build failed"))

    try:
        import asyncio

        asyncio.run(_stream())
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc


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
        return

    click.echo("")
    click.echo(f"  {_('Apeiria environment initialized')}")
    click.echo("")

    if result.created:
        names = ", ".join(result.created)
        click.echo(
            f"  {_('Configs'):10s} {len(result.created)} {_('created')} ({names})"
        )
    if result.skipped:
        click.echo(
            f"  {_('Configs'):10s} {len(result.skipped)}"
            f" {_('skipped (already exists)')}"
        )

    click.echo(f"  {_('Python'):10s} {_('dependencies synced')}")
    click.echo(f"  {_('Plugins'):10s} {_('extension project ready')}")
    click.echo("")

    click.echo(f"  {_('Next steps')}:")
    click.echo(f"    uv run apeiria run              # {_('start the bot')}")
    click.echo(
        f"    uv run apeiria webui recover    # {_('create admin account for Web UI')}"
    )
    click.echo("")


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


@click.command(
    context_settings={"ignore_unknown_options": True},
    help=_("Run the canonical Apeiria runtime entry."),
)
@click.option(
    "--build",
    "build_frontend_first",
    is_flag=True,
    help=_("Build Web UI frontend assets before running the bot."),
)
@click.option(
    "--entry",
    "entry_file",
    default=None,
    help=_("Retired. Use user_bot.py for project-local startup customization."),
)
@click.option(
    "--reload",
    is_flag=True,
    help=_("Restart the Apeiria entry process when project files change."),
)
@click.argument("extra_args", nargs=-1)
def run(
    *,
    build_frontend_first: bool,
    entry_file: str,
    reload: bool,
    extra_args: tuple[str, ...],
) -> None:
    if entry_file is not None:
        raise click.ClickException(
            _(
                "custom entry files are retired; use `apeiria run` and "
                "`user_bot.py` for project-local customization"
            )
        )
    root = project_root()
    _auto_prepare_run(root, build_frontend_first=build_frontend_first)
    if reload:
        raise click.exceptions.Exit(run_with_reload(cwd=root, extra_args=extra_args))
    env = _runtime_process_env(root)
    result = subprocess.run(
        [sys.executable, "-m", "apeiria.bot.entry", *extra_args],
        cwd=root,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        raise click.exceptions.Exit(result.returncode)


_AUTO_PREPARE_FRONTEND_DETAILS = frozenset(
    {"dist_missing", "build_meta_missing", "fingerprint_missing", "stale"}
)


def _auto_prepare_run(
    root: Path,
    *,
    build_frontend_first: bool,
) -> None:
    from apeiria.environment.health import HealthService
    from apeiria.environment.manager import EnvironmentService

    service = EnvironmentService(project_root=root)
    snapshot = HealthService(service).get_snapshot()
    checks = {check.key: check for check in snapshot.checks}

    _auto_prepare_env(checks)
    _auto_prepare_db(checks)
    _auto_prepare_frontend(
        checks,
        build_frontend_first=build_frontend_first,
    )


def _auto_prepare_env(checks: dict[str, object]) -> None:
    from apeiria.environment.models import HealthCheck

    config_keys = ("main_config", "plugin_config", "adapter_config", "driver_config")
    ok_check = HealthCheck(key="ok", ok=True, detail="ok", message="ok")

    needs_init = any(
        not getattr(checks.get(key, ok_check), "ok", True) for key in config_keys
    )
    if needs_init:
        click.echo(_("preparing environment for first run ..."))
        try:
            initialize_user_environment()
        except RuntimeError as exc:
            raise_click_runtime_error(exc)
            return
        click.echo("")

    venv_check = checks.get("main_venv")
    if venv_check is not None and not getattr(venv_check, "ok", True):
        click.echo(_("preparing environment for first run ..."))
        try:
            initialize_user_environment()
        except RuntimeError as exc:
            raise_click_runtime_error(exc)
            return
        click.echo("")

    ext_check = checks.get("extension_project")
    if ext_check is not None and not getattr(ext_check, "ok", True):
        click.echo(_("repairing extension project ..."))
        try:
            repair_user_environment()
        except RuntimeError as exc:
            raise_click_runtime_error(exc)
            return
        click.echo("")


def _auto_prepare_db(checks: dict[str, object]) -> None:
    from apeiria.environment.models import HealthCheck

    ok_check = HealthCheck(key="ok", ok=True, detail="ok", message="ok")
    db_check = checks.get("database", ok_check)
    if not getattr(db_check, "ok", True):
        click.echo(_("repairing database ..."))
        try:
            repair_database_schema()
        except click.ClickException:
            raise
        except Exception as exc:
            raise click.ClickException(
                _("database repair failed: {error}").format(error=str(exc))
            ) from exc
        click.echo("")


def _auto_prepare_frontend(
    checks: dict[str, object],
    *,
    build_frontend_first: bool,
) -> None:
    from apeiria.environment.models import HealthCheck

    ok_check = HealthCheck(key="ok", ok=True, detail="ok", message="ok")
    frontend_check = checks.get("frontend_build", ok_check)
    frontend_needs_build = build_frontend_first or (
        not getattr(frontend_check, "ok", True)
        and getattr(frontend_check, "detail", "") in _AUTO_PREPARE_FRONTEND_DETAILS
    )
    if frontend_needs_build:
        click.echo(_("building Web UI frontend ..."))
        try:
            build_frontend()
        except click.ClickException:
            raise
        except Exception as exc:
            raise click.ClickException(
                _("frontend build failed: {error}").format(error=str(exc))
            ) from exc
        click.echo("")


def run_with_reload(
    *,
    cwd: Path,
    extra_args: tuple[str, ...],
) -> int:
    from watchfiles import run_process

    return run_process(
        cwd,
        target=_run_entry_once,
        args=(cwd, extra_args),
    )


def _run_entry_once(
    cwd: Path,
    extra_args: tuple[str, ...],
) -> int:
    env = _runtime_process_env(cwd)
    return subprocess.run(
        [sys.executable, "-m", "apeiria.bot.entry", *extra_args],
        cwd=cwd,
        check=False,
        env=env,
    ).returncode


def _runtime_process_env(project_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env[runtime_project_root_env_var()] = str(project_root.resolve())
    return env


@env.command("info", help=_("Show current Apeiria environment paths and status."))
@click.option("--json", "json_output", is_flag=True, help=_("Emit JSON output."))
def env_info(*, json_output: bool) -> None:
    snapshot = active_environment_service().get_environment_snapshot()
    if json_output:
        echo_json(snapshot)
        return
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
    snapshot = active_health_service().get_snapshot()
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
        return _("run `apeiria env init`")

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
            "is not supported by this apeiria build",
            "move the current local database aside and rerun check to recreate it",
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
@click.option("--json", "json_output", is_flag=True, help=_("Emit JSON output."))
def env_doctor(*, json_output: bool) -> None:
    if json_output:
        echo_json(active_health_service().get_snapshot())
        return
    _echo_system_health(include_checks=True)


@click.command(help=_("Show Apeiria system health summary."))
@click.option("--json", "json_output", is_flag=True, help=_("Emit JSON output."))
def status(*, json_output: bool) -> None:
    if json_output:
        echo_json(active_health_service().get_snapshot())
        return
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
    target_root, copied = active_environment_service().export_runtime_state(
        Path(output_dir) if output_dir else None
    )
    click.echo(_("exported files: {count}").format(count=copied))
    click.echo(_("export target: {target}").format(target=target_root))


@env.command("import", help=_("Import local runtime state from a migration bundle."))
@click.argument("input_dir")
def env_import(input_dir: str) -> None:
    try:
        _target_root, copied = active_environment_service().import_runtime_state(
            Path(input_dir)
        )
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(_("imported files: {count}").format(count=copied))

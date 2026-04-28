from __future__ import annotations

import click

from apeiria.cli.context import active_environment_service
from apeiria.cli.i18n import _
from apeiria.cli.output import echo_json
from apeiria.db.inspection import DatabaseInspection, inspect_database


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help=_("Inspect and repair the Apeiria project database."),
)
def db() -> None:
    """Inspect and repair the Apeiria project database."""


@db.command("status", help=_("Show Apeiria database path and schema status."))
@click.option("--json", "json_output", is_flag=True, help=_("Emit JSON output."))
def db_status(*, json_output: bool) -> None:
    inspection = _inspect_active_database()
    if json_output:
        echo_json(inspection)
        return
    _echo_database_status(inspection)


@db.command("check", help=_("Check database readiness without mutating it."))
@click.option("--json", "json_output", is_flag=True, help=_("Emit JSON output."))
def db_check(*, json_output: bool) -> None:
    inspection = _inspect_active_database()
    payload = {
        "ready": inspection.ready,
        "project_root": inspection.project_root,
        "path": inspection.path,
        "exists": inspection.exists,
        "schema": inspection.schema,
    }
    if json_output:
        echo_json(payload)
    else:
        _echo_database_status(inspection)
    if not inspection.ready:
        raise click.exceptions.Exit(1)


@db.command("repair", help=_("Create or repair the Apeiria database schema."))
@click.option("--json", "json_output", is_flag=True, help=_("Emit JSON output."))
def db_repair(*, json_output: bool) -> None:
    try:
        active_environment_service().repair_database_schema()
    except Exception as exc:
        raise click.ClickException(
            _("database repair failed: {error}").format(error=str(exc))
        ) from exc
    inspection = _inspect_active_database()
    if json_output:
        echo_json(
            {
                "repaired": inspection.ready,
                "project_root": inspection.project_root,
                "path": inspection.path,
                "exists": inspection.exists,
                "schema": inspection.schema,
            }
        )
        return
    click.echo(_("repaired database"))
    _echo_database_status(inspection)


def _inspect_active_database() -> DatabaseInspection:
    return inspect_database(active_environment_service().project_root)


def _echo_database_status(inspection: DatabaseInspection) -> None:
    schema = inspection.schema
    click.echo(f"path={inspection.path}")
    click.echo(f"exists={inspection.exists}")
    click.echo(f"ready={inspection.ready}")
    click.echo(f"schema_status={schema.status}")
    click.echo(f"schema_line={schema.schema_line or '-'}")
    click.echo(f"schema_version={schema.schema_version or '-'}")
    click.echo(f"head_revision={schema.head_revision}")
    if schema.detail:
        click.echo(f"detail={schema.detail}")

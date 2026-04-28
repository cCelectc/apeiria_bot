from __future__ import annotations

import click

from apeiria.cli.commands.db import db
from apeiria.cli.commands.env import check, env, init, repair, run, status
from apeiria.cli.commands.resource import adapter, driver, plugin
from apeiria.cli.commands.webui import webui
from apeiria.cli.context import initialize_cli_context
from apeiria.cli.i18n import _


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--cwd",
    type=click.Path(file_okay=False, dir_okay=True),
    help=_("Run host-side commands against this Apeiria project root."),
)
@click.pass_context
def cli(ctx: click.Context, cwd: str | None) -> None:
    """Apeiria project tools."""
    initialize_cli_context(ctx, cwd=cwd)


cli.add_command(env)
cli.add_command(init)
cli.add_command(repair)
cli.add_command(run)
cli.add_command(status)
cli.add_command(check)
cli.add_command(db)
cli.add_command(plugin)
cli.add_command(adapter)
cli.add_command(driver)
cli.add_command(webui)


def main() -> None:
    cli(prog_name="apeiria")


if __name__ == "__main__":
    main()

from __future__ import annotations

import click

from apeiria.cli.commands.env import check, env, init, repair, run, status
from apeiria.cli.commands.resource import adapter, driver, plugin
from apeiria.cli.commands.webui import webui


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    """Apeiria project tools."""


cli.add_command(env)
cli.add_command(init)
cli.add_command(repair)
cli.add_command(run)
cli.add_command(status)
cli.add_command(check)
cli.add_command(plugin)
cli.add_command(adapter)
cli.add_command(driver)
cli.add_command(webui)


def main() -> None:
    cli(prog_name="apeiria")


if __name__ == "__main__":
    main()

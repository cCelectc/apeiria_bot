from __future__ import annotations

import click

from apeiria.cli.init_cmd import init_cmd
from apeiria.cli.run_cmd import run_cmd


@click.group()
@click.option(
    "-c",
    "--cwd",
    default=None,
    help="Project root directory",
)
@click.pass_context
def cli(_ctx: click.Context, cwd: str | None) -> None:
    if cwd is not None:
        import os
        from pathlib import Path

        os.chdir(Path(cwd).resolve())


cli.add_command(init_cmd)
cli.add_command(run_cmd)


def main() -> None:
    cli()

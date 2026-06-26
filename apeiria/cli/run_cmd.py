from __future__ import annotations

import click

from apeiria.bootstrap.plan import BootstrapPlan
from apeiria.bootstrap.steps import (
    step_access,
    step_apeiria_ensure,
    step_apeiria_inject,
    step_apeiria_sync,
    step_conversation,
    step_db_migrate,
    step_load_builtins,
    step_load_local,
    step_load_pypi,
    step_web,
)
from apeiria.config.loader import expand_config, load_config
from apeiria.db.engine import init_db


@click.command("run")
@click.option("--reload", is_flag=True, default=False, help="Enable hot reload")
def run_cmd(reload: bool) -> None:  # noqa: FBT001
    app = load_config("data/config.yaml")
    expand_config(app)

    import nonebot

    nonebot.init()

    db_path = app.apeiria.database.path
    import asyncio

    asyncio.run(init_db(f"sqlite+aiosqlite:///{db_path}"))

    plan = BootstrapPlan()
    plan.add_step("db_migrate", step_db_migrate)
    plan.add_step("apeiria_ensure", step_apeiria_ensure)
    plan.add_step("apeiria_sync", step_apeiria_sync, depends=["apeiria_ensure"])
    plan.add_step("apeiria_inject", step_apeiria_inject, depends=["apeiria_sync"])
    plan.add_step("load_builtins", step_load_builtins, depends=["apeiria_inject"])
    plan.add_step("load_local", step_load_local, depends=["apeiria_inject"])
    plan.add_step("load_pypi", step_load_pypi, depends=["apeiria_inject"])
    plan.add_step(
        "conversation",
        step_conversation,
        depends=["load_builtins", "load_local"],
    )
    plan.add_step("access", step_access, depends=["load_builtins", "load_local"])
    plan.add_step("web", step_web, depends=["access"])

    plan.run("full")

    if reload:
        from pathlib import Path

        import watchfiles

        click.echo("Hot reload enabled — watching for changes...")
        for _changes in watchfiles.watch(
            Path("apeiria"), Path(".apeiria/plugins"), Path("data/config.yaml")
        ):
            click.echo("Changes detected — restart with 'apeiria run' again")
            break
    else:
        nonebot.run()

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
    step_load_adapters,
    step_load_builtin_adapters,
    step_load_builtins,
    step_load_local,
    step_load_pypi,
    step_web,
    step_webchat,
)
from apeiria.config.loader import expand_config, load_config
from apeiria.db.engine import init_db

GRACEFUL_SHUTDOWN_TIMEOUT = 3


@click.command("run")
@click.option("--reload", is_flag=True, default=False, help="Enable hot reload")
def run_cmd(reload: bool) -> None:  # noqa: FBT001
    import nonebot

    from apeiria.web.logs import get_log_hub

    app = load_config("data/config.yaml")
    get_log_hub().install_sinks(app.apeiria.logging)
    expand_config(app)

    nonebot.init()

    db_path = app.apeiria.database.path
    import asyncio

    asyncio.run(init_db(f"sqlite+aiosqlite:///{db_path}"))

    plan = BootstrapPlan()
    plan.add_step("db_migrate", step_db_migrate)
    plan.add_step("apeiria_ensure", step_apeiria_ensure)
    plan.add_step("apeiria_sync", step_apeiria_sync, depends=["apeiria_ensure"])
    plan.add_step("apeiria_inject", step_apeiria_inject, depends=["apeiria_sync"])
    plan.add_step(
        "load_builtin_adapters",
        step_load_builtin_adapters,
        depends=["apeiria_ensure"],
    )
    plan.add_step("load_adapters", step_load_adapters, depends=["apeiria_inject"])
    plan.add_step(
        "load_builtins",
        step_load_builtins,
        depends=["load_adapters", "load_builtin_adapters"],
    )
    plan.add_step(
        "load_local",
        step_load_local,
        depends=["load_adapters", "load_builtin_adapters"],
    )
    plan.add_step(
        "load_pypi",
        step_load_pypi,
        depends=["load_adapters", "load_builtin_adapters"],
    )
    plan.add_step(
        "conversation",
        step_conversation,
        depends=["load_builtins", "load_local"],
    )
    plan.add_step("access", step_access, depends=["load_builtins", "load_local"])
    plan.add_step("webchat", step_webchat, depends=["conversation", "access"])
    plan.add_step("web", step_web, depends=["access", "webchat"])

    plan.run("full")

    if reload:
        from pathlib import Path

        import watchfiles

        click.echo("Hot reload enabled — watching for changes...")
        for _changes in watchfiles.watch(
            Path("apeiria"),
            Path(".apeiria/plugins"),
            Path("data/config.yaml"),
        ):
            click.echo("Changes detected — restart with 'apeiria run' again")
            break
    else:
        nonebot.run(timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_TIMEOUT)

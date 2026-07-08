from __future__ import annotations

import click


@click.command("reset-password")
@click.option(
    "--password",
    default=None,
    help="Set a specific password (a strong one is generated if omitted)",
)
def reset_password_cmd(password: str | None) -> None:
    import asyncio

    from apeiria.config.loader import load_config
    from apeiria.db.engine import init_db
    from apeiria.web.auth import reset_password
    from apeiria.web.auth_password import validate_dashboard_password

    if password is not None:
        try:
            validate_dashboard_password(password)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc

    app = load_config("data/config.yaml")
    db_path = app.apeiria.database.path
    asyncio.run(init_db(f"sqlite+aiosqlite:///{db_path}"))

    plaintext = reset_password(password)
    click.echo("管理员密码已重置：")
    click.echo(f"  密码：{plaintext}")
    click.echo("（请妥善保存；若机器人正在运行，需重启后生效）")

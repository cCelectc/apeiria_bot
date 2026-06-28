from __future__ import annotations

import click

from apeiria.env.ensure import ensure_apeiria_env


@click.command("init")
def init_cmd() -> None:
    click.echo("Apeiria Bot — project initialization\n")

    nickname = click.prompt("Bot nickname", default="Bot")
    admin_id = click.prompt("Admin ID (cross-platform, comma separated)", default="")

    ensure_apeiria_env()

    admin_ids = [x.strip() for x in admin_id.split(",") if x.strip()]
    config_lines = [
        "nonebot:",
        '  host: "127.0.0.1"',
        "  port: 8080",
        '  command_start: ["/"]',
        '  command_sep: ["."]',
        f"  nickname: [{nickname!r}]",
        f"  superusers: {admin_ids!r}",
        '  locale: "zh_CN"',
        '  log_level: "INFO"',
        "",
        "plugins: {}",
        "",
        "adapters:",
        "  nonebot_adapter_onebot_v11: {}",
        "",
        "apeiria:",
        "  database:",
        '    path: "data/apeiria.db"',
        "  web:",
        '    host: "127.0.0.1"',
        "    port: 8080",
    ]
    from pathlib import Path

    config_path = Path("data/config.yaml")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("\n".join(config_lines) + "\n", encoding="utf-8")

    env_path = Path(".env")
    if not env_path.exists():
        env_path.write_text(
            "# Apeiria Bot — 兜底配置，主配置见 data/config.yaml\n", encoding="utf-8"
        )

    click.echo(f"\nProject initialized. Config: {config_path}")
    click.echo("Run 'apeiria run' to start the bot.")

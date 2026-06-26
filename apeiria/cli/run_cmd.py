from __future__ import annotations

from apeiria.config.loader import expand_config, load_config


def run_bot() -> None:
    app = load_config("data/config.yaml")
    expand_config(app)

    import nonebot

    nonebot.init()
    nonebot.run()

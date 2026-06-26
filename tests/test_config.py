from __future__ import annotations


def test_config_defaults() -> None:
    from apeiria.config.models import AppConfig

    app = AppConfig()
    assert app.nonebot.host == "127.0.0.1"
    assert app.apeiria.database.path == "data/apeiria.db"


def test_expand_config_env() -> None:
    import os

    from apeiria.config.loader import expand_config
    from apeiria.config.models import AppConfig

    app = AppConfig()
    app.nonebot.host = "10.0.0.1"
    app.plugins = {"help": {"expand_commands": True}}

    expand_config(app)
    assert os.environ["HOST"] == "10.0.0.1"
    assert os.environ["EXPAND_COMMANDS"] == "1"
    del os.environ["HOST"]
    del os.environ["EXPAND_COMMANDS"]

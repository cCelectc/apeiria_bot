from __future__ import annotations

import os


def test_config_defaults() -> None:
    from apeiria.config.models import AppConfig

    app = AppConfig()
    assert app.nonebot.host == "127.0.0.1"
    assert app.apeiria.database.path == "data/apeiria.db"


def test_expand_config_env() -> None:
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


def test_flatten_nested() -> None:
    from apeiria.config.loader import _flatten_nested

    cfg = {"api_key": "sk-xxx", "db": {"host": "localhost", "port": 5432}}
    _flatten_nested("WEATHER", cfg)

    assert os.environ["WEATHER__API_KEY"] == "sk-xxx"
    assert os.environ["WEATHER__DB__HOST"] == "localhost"
    assert os.environ["WEATHER__DB__PORT"] == "5432"

    del os.environ["WEATHER__API_KEY"]
    del os.environ["WEATHER__DB__HOST"]
    del os.environ["WEATHER__DB__PORT"]


def test_flatten_nested_deep() -> None:
    from apeiria.config.loader import _flatten_nested

    cfg = {"a": {"b": {"c": 1}}}
    _flatten_nested("P", cfg)
    assert os.environ["P__A__B__C"] == "1"
    del os.environ["P__A__B__C"]

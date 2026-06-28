from __future__ import annotations

import os
from types import SimpleNamespace


def _isolate_env(monkeypatch) -> None:
    monkeypatch.setattr(os, "environ", dict(os.environ))


def test_to_env_value() -> None:
    from apeiria.config.loader import to_env_value

    yes, no = True, False
    assert to_env_value("s") == "s"
    assert to_env_value(yes) == "1"
    assert to_env_value(no) == "0"
    assert to_env_value(123) == "123"
    assert to_env_value(["a"]) == '["a"]'


def test_expand_config_injects_nonebot_not_apeiria(monkeypatch) -> None:
    from apeiria.config.loader import expand_config
    from apeiria.config.models import (
        ApeiriaConfig,
        AppConfig,
        DatabaseConfig,
        NoneBotConfig,
    )

    _isolate_env(monkeypatch)
    app = AppConfig(
        nonebot=NoneBotConfig(host="9.9.9.9", port=4321),
        apeiria=ApeiriaConfig(
            database=DatabaseConfig(path="SENTINEL_APEIRIA_PATH_XYZ")
        ),
    )
    expand_config(app)

    assert os.environ["HOST"] == "9.9.9.9"
    assert os.environ["PORT"] == "4321"
    assert not any("SENTINEL_APEIRIA_PATH_XYZ" in v for v in os.environ.values())


def test_update_runtime_config_updates_env_and_driver(monkeypatch) -> None:
    from apeiria.config.loader import update_runtime_config
    from apeiria.config.models import AppConfig

    _isolate_env(monkeypatch)
    fake_config = SimpleNamespace()
    monkeypatch.setattr(
        "nonebot.get_driver", lambda: SimpleNamespace(config=fake_config)
    )

    app = AppConfig(plugins={"zzz_unknown_plugin": {"some_key": "val"}})
    update_runtime_config(app)

    assert os.environ["SOME_KEY"] == "val"
    assert fake_config.some_key == "val"

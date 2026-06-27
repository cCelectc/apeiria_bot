from __future__ import annotations

from pydantic import BaseModel

from apeiria.plugin.adapter_resolver import _find_config_in_module


def test_find_config_in_known_module() -> None:
    config_cls = _find_config_in_module("nonebot.adapters.console")
    if config_cls is not None:
        assert issubclass(config_cls, BaseModel)


def test_find_config_no_config_module_returns_none() -> None:
    result = _find_config_in_module("json")
    assert result is None

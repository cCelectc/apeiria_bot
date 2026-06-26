from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RepeaterConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    probability: float = 0.3
    cooldown_seconds: int = 60
    repeat_threshold: int = 2
    allowlist: list[str] = []
    blocklist: list[str] = []


def get_plugin_config() -> RepeaterConfig:
    from nonebot import get_plugin_config as _get_plugin_config

    return _get_plugin_config(RepeaterConfig)


__all__ = ["RepeaterConfig", "get_plugin_config"]

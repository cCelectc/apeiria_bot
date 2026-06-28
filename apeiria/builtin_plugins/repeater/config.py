from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RepeaterConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    probability: float = Field(default=0.3, ge=0.0, le=1.0)
    cooldown_seconds: int = Field(default=60, ge=1)
    repeat_threshold: int = Field(default=2, ge=2)
    allowlist: list[str] = []
    blocklist: list[str] = []


def get_plugin_config() -> RepeaterConfig:
    from nonebot import get_plugin_config as _get_plugin_config

    return _get_plugin_config(RepeaterConfig)


__all__ = ["RepeaterConfig", "get_plugin_config"]

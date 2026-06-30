from __future__ import annotations

from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict


class RelayConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    target: str = ""
    rate_limit_count: int = 3
    rate_limit_window: float = 60.0
    message_prefix: str = ""


def get_relay_config() -> RelayConfig:
    return get_plugin_config(RelayConfig)

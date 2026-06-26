from __future__ import annotations

from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict


class TriggerReplyConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: bool = True
    priority: int = 12
    rules_file: str = "rules.toml"
    debug: bool = False


def get_trigger_reply_config() -> TriggerReplyConfig:
    return get_plugin_config(TriggerReplyConfig)

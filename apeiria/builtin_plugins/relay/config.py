from __future__ import annotations

from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict, Field


class RelayConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target: str = Field(
        default="",
        description="传话目标，格式 scope:id（如 QQClient:123456），留空则投递给超管",
    )
    rate_limit_count: int = Field(
        default=3, description="滑动窗口内最大传话次数，0=不限流"
    )
    rate_limit_window: float = Field(default=60.0, description="限流滑动窗口秒数")
    message_prefix: str = Field(default="", description="转发时添加在消息前的文本")


def get_relay_config() -> RelayConfig:
    return get_plugin_config(RelayConfig)

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RepeaterConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    probability: float = Field(
        default=0.3, ge=0.0, le=1.0, description="达到复读阈值后的复读概率"
    )
    cooldown_seconds: int = Field(
        default=60, ge=1, description="同群同内容复读一次后的冷却秒数"
    )
    repeat_threshold: int = Field(
        default=2, ge=2, description="连续不同用户发送相同内容触发复读的阈值"
    )
    allowlist: list[str] = Field(
        default_factory=list,
        description="允许生效的群，格式 scope:group_id，为空所有群生效",
    )
    blocklist: list[str] = Field(
        default_factory=list,
        description="禁止生效的群，格式 scope:group_id，冲突时优先",
    )


def get_plugin_config() -> RepeaterConfig:
    from nonebot import get_plugin_config as _get_plugin_config

    return _get_plugin_config(RepeaterConfig)


__all__ = ["RepeaterConfig", "get_plugin_config"]

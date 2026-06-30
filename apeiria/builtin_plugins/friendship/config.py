from __future__ import annotations

from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict


class FriendshipConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: bool = True
    notify_superusers: bool = True
    auto_approve: bool = False


def get_friendship_config() -> FriendshipConfig:
    return get_plugin_config(FriendshipConfig)

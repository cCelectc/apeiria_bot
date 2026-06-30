from __future__ import annotations

from typing import Literal

from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict, Field

SelfRevokePermission = Literal["public", "superuser"]
SelfRevokeFeedback = Literal["silent", "reaction"]


class SelfRevokeConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    permission: SelfRevokePermission = Field(
        default="public", description="撤回权限：public=所有人，superuser=仅超管"
    )
    revoke_trigger_message: bool = Field(
        default=False, description="是否同时撤回触发消息本身"
    )
    feedback: SelfRevokeFeedback = Field(
        default="silent", description="操作反馈方式：silent=静默，reaction=表情反应"
    )


def get_self_revoke_config() -> SelfRevokeConfig:
    return get_plugin_config(SelfRevokeConfig)

from __future__ import annotations

from typing import Literal

from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict

SelfRevokePermission = Literal["public", "superuser"]
SelfRevokeFeedback = Literal["silent", "reaction"]


class SelfRevokeConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    permission: SelfRevokePermission = "public"
    revoke_trigger_message: bool = False
    feedback: SelfRevokeFeedback = "silent"


def get_self_revoke_config() -> SelfRevokeConfig:
    return get_plugin_config(SelfRevokeConfig)

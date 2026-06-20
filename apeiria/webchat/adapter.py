"""Adapter type for WebChat."""

from __future__ import annotations

from typing import Any

from nonebot.adapters import Adapter, Bot


class WebChatAdapter(Adapter):
    @classmethod
    def get_name(cls) -> str:
        return "WebChat"

    async def _call_api(self, bot: Bot, api: str, **data: Any) -> Any:  # noqa: ARG002
        return None

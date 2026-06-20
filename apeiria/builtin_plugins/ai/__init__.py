from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot import on_message
from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.plugin import PluginMetadata

if TYPE_CHECKING:
    from apeiria.builtin_plugins.ai.rhythm import RhythmManager

__plugin_meta__ = PluginMetadata(
    name="Apeiria AI",
    description="AI conversation engine",
    usage="Automatic AI responses",
)

import apeiria.builtin_plugins.ai.commands  # noqa: F401

_msg_handler = on_message(priority=10, block=False)


@_msg_handler.handle()
async def handle_message(bot: Bot, event: Event) -> None:
    from apeiria.builtin_plugins.ai.shell import extract_event_info

    info = extract_event_info(bot, event)

    _ensure_rhythm_manager()
    if _rhythm_manager:
        _rhythm_manager.on_message(
            info["session_id"],
            info,
            is_at_bot=info["is_at_bot"],
            is_private=info["is_private"],
        )


_rhythm_manager = None


def _ensure_rhythm_manager() -> None:
    global _rhythm_manager  # noqa: PLW0603
    if _rhythm_manager is None:
        from apeiria.ai.agent.registry import AgentRegistry
        from apeiria.builtin_plugins.ai.rhythm import RhythmManager

        _rhythm_manager = RhythmManager(AgentRegistry())


def get_rhythm_manager() -> RhythmManager | None:
    _ensure_rhythm_manager()
    return _rhythm_manager

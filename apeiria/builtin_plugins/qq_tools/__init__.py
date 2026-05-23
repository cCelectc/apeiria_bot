"""QQ AI tool built-in plugin shell."""

from __future__ import annotations

from nonebot.plugin import PluginMetadata

from apeiria.ai.plugin_api import ai_skill_source
from apeiria.plugins.metadata.api import (
    HelpExtra,
    PluginExtraData,
    PluginType,
    UiExtra,
)

__plugin_meta__ = PluginMetadata(
    name="QQ Tools",
    description="Small AI capability pack for bounded QQ chat actions.",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage="Provides AI tools only; no chat command is registered.",
    type="application",
    supported_adapters=None,
    extra=PluginExtraData(
        author="apeiria",
        version="0.1.0",
        plugin_type=PluginType.NORMAL,
        help=HelpExtra(
            category="AI",
            introduction="让 AI 在明确有价值时使用少量 QQ 聊天动作。",
        ),
        ui=UiExtra(label="QQ Tools", order=16),
    ).to_dict(),
)

ai_skill_source("skills/qq-tools/SKILL.md")

from . import tools as tools

__all__ = ["tools"]

from __future__ import annotations

from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict, Field


class HelpConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(default="功能菜单", description="主标题")
    subtitle: str = Field(default="", description="副标题")
    accent_color: str = Field(default="#4e96f7", description="主题强调色")
    expand_commands: bool = Field(default=False, description="是否在主菜单展开命令")
    show_builtin_plugins: bool = Field(default=False, description="是否显示内置插件")
    hidden_plugins: list[str] = Field(
        default_factory=list, description="隐藏的插件名称列表"
    )


def get_help_config() -> HelpConfig:
    return get_plugin_config(HelpConfig)

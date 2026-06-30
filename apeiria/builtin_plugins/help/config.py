from __future__ import annotations

from typing import Literal

from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict, Field


class PluginOverride(BaseModel):
    plugin_name: str = Field(default="", description="插件名")
    display_name: str = Field(default="", description="覆盖的显示名称")
    description: str = Field(default="", description="覆盖的描述")
    category: str = Field(default="", description="覆盖的分类")
    order: int = Field(default=99, description="覆盖的排序")
    extra_commands: list[str] = Field(default_factory=list, description="额外命令")


class HelpAppearanceConfig(BaseModel):
    title: str = Field(default="", description="主标题")
    subtitle: str = Field(default="", description="副标题")
    accent_color: str = Field(default="#4e96f7", description="主题强调色")
    expand_commands: bool = Field(default=False, description="是否在主菜单展开命令")


class HelpVisibilityConfig(BaseModel):
    show_builtin_plugins: bool = Field(default=False, description="是否显示内置插件")
    hidden_plugins: list[str] = Field(
        default_factory=list, description="隐藏的插件名称列表"
    )


class HelpRoleConfig(BaseModel):
    enabled: bool = Field(default=True, description="是否启用角色视图")
    mode: Literal["auto", "manual_only"] = Field(
        default="auto", description="角色模式：auto=自动，manual_only=手动切换"
    )
    owner_sees_all: bool = Field(default=False, description="主人是否可见全部插件")
    user_title: str = Field(default="", description="用户视图标题")
    admin_title: str = Field(default="", description="管理员视图标题")
    owner_title: str = Field(default="", description="主人视图标题")


class HelpAssetsConfig(BaseModel):
    banner_image: str = Field(default="", description="横幅图片 URL")
    header_logo: str = Field(default="", description="Logo 图片 URL")
    footer_text: str = Field(default="", description="页脚文本")
    font_urls: list[str] = Field(default_factory=list, description="远程字体 URL 列表")
    font_family: str = Field(default="", description="中文字体")
    latin_font_family: str = Field(default="", description="拉丁字体")
    mono_font_family: str = Field(default="", description="等宽字体")


class HelpRenderConfig(BaseModel):
    prefer_custom_templates: bool = Field(
        default=False, description="是否优先使用自定义模板"
    )
    disk_cache: bool = Field(default=False, description="是否启用磁盘缓存")
    debug: bool = Field(default=False, description="是否落渲染 HTML/数据便于排查")


class HelpConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    appearance: HelpAppearanceConfig = Field(
        default_factory=HelpAppearanceConfig, description="外观设置"
    )
    visibility: HelpVisibilityConfig = Field(
        default_factory=HelpVisibilityConfig, description="可见性控制"
    )
    roles: HelpRoleConfig = Field(
        default_factory=HelpRoleConfig, description="角色视图配置"
    )
    assets: HelpAssetsConfig = Field(
        default_factory=HelpAssetsConfig, description="静态资源配置"
    )
    render: HelpRenderConfig = Field(
        default_factory=HelpRenderConfig, description="渲染相关配置"
    )
    plugin_overrides: list[PluginOverride] = Field(
        default_factory=list, description="插件显示覆盖"
    )

    @property
    def title(self) -> str:
        return self.appearance.title

    @property
    def subtitle(self) -> str:
        return self.appearance.subtitle

    @property
    def accent_color(self) -> str:
        return self.appearance.accent_color

    @property
    def expand_commands(self) -> bool:
        return self.appearance.expand_commands

    @property
    def show_builtin_cmds(self) -> bool:
        return self.visibility.show_builtin_plugins

    @property
    def plugin_blacklist(self) -> list[str]:
        return self.visibility.hidden_plugins

    @property
    def admin_show_all(self) -> bool:
        return self.roles.owner_sees_all

    @property
    def enable_role_views(self) -> bool:
        return self.roles.enabled

    @property
    def role_view_mode(self) -> Literal["auto", "manual_only"]:
        return self.roles.mode

    @property
    def user_title(self) -> str:
        return self.roles.user_title

    @property
    def admin_title(self) -> str:
        return self.roles.admin_title

    @property
    def owner_title(self) -> str:
        return self.roles.owner_title

    @property
    def banner_image(self) -> str:
        return self.assets.banner_image

    @property
    def header_logo(self) -> str:
        return self.assets.header_logo

    @property
    def footer_text(self) -> str:
        return self.assets.footer_text

    @property
    def font_urls(self) -> list[str]:
        return self.assets.font_urls

    @property
    def font_family(self) -> str:
        return self.assets.font_family

    @property
    def latin_font_family(self) -> str:
        return self.assets.latin_font_family

    @property
    def mono_font_family(self) -> str:
        return self.assets.mono_font_family

    @property
    def custom_templates(self) -> bool:
        return self.render.prefer_custom_templates

    @property
    def disk_cache(self) -> bool:
        return self.render.disk_cache

    @property
    def debug(self) -> bool:
        return self.render.debug


def get_help_config() -> HelpConfig:
    return get_plugin_config(HelpConfig)

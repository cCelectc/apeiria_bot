from __future__ import annotations

from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from apeiria.config import project_config_service

ModelT = TypeVar("ModelT", bound=BaseModel)


class PluginOverride(BaseModel):
    plugin_name: str = ""
    display_name: str = ""
    description: str = ""
    category: str = ""
    order: int = 99
    extra_commands: list[str] = Field(default_factory=list)


class HelpAppearanceConfig(BaseModel):
    title: str = ""
    subtitle: str = ""
    accent_color: str = "#4e96f7"
    expand_commands: bool = False


class HelpVisibilityConfig(BaseModel):
    show_builtin_plugins: bool = False
    hidden_plugins: list[str] = Field(default_factory=list)


class HelpRoleConfig(BaseModel):
    enabled: bool = True
    mode: Literal["auto", "manual_only"] = "auto"
    owner_sees_all: bool = False
    user_title: str = ""
    admin_title: str = ""
    owner_title: str = ""


class HelpAssetsConfig(BaseModel):
    banner_image: str = ""
    header_logo: str = ""
    footer_text: str = ""
    font_urls: list[str] = Field(default_factory=list)
    font_family: str = ""
    latin_font_family: str = ""
    mono_font_family: str = ""


class HelpRenderConfig(BaseModel):
    prefer_custom_templates: bool = False
    disk_cache: bool = False
    debug: bool = False


class HelpConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    appearance: HelpAppearanceConfig = Field(default_factory=HelpAppearanceConfig)
    visibility: HelpVisibilityConfig = Field(default_factory=HelpVisibilityConfig)
    roles: HelpRoleConfig = Field(default_factory=HelpRoleConfig)
    assets: HelpAssetsConfig = Field(default_factory=HelpAssetsConfig)
    render: HelpRenderConfig = Field(default_factory=HelpRenderConfig)
    plugin_overrides: list[PluginOverride] = Field(default_factory=list)

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


def _validate_config(model: type[ModelT], data: dict[str, object]) -> ModelT:
    return model.model_validate(data)


def get_help_config() -> HelpConfig:
    config = project_config_service.read_project_plugin_config("help")
    return _validate_config(HelpConfig, config)

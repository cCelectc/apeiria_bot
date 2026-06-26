"""Help plugin — auto-generated command help system (v2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot import require
from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.plugin import PluginMetadata, inherit_supported_adapters
from nonebot_plugin_alconna import (
    Alconna,
    Args,
    CommandMeta,
    Match,
    MultiVar,
    on_alconna,
)

require("nonebot_plugin_htmlrender")

from apeiria.plugin.metadata.api import (
    ConfigExtra,
    HelpExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)
from apeiria.utils.superuser import is_superuser_id

from .commands import _cmd_prefix
from .config import HelpConfig, get_help_config
from .renderer import (
    _show_detail,
    _show_menu,
)

if TYPE_CHECKING:
    from .models import HelpViewRole

# ── help command ───────────────────────────────────────────────────────────

_help = on_alconna(
    Alconna(
        "help",
        Args["plugin_name?", MultiVar(str, "*")],
        meta=CommandMeta(description="查看功能菜单"),
    ),
    aliases={"帮助", "菜单", "功能"},
    use_cmd_start=True,
    priority=1,
    block=True,
)


async def _resolve_role(
    event: Event,
    *,
    config: HelpConfig,
    force_admin: bool,
    force_owner: bool,
) -> HelpViewRole:
    is_owner = is_superuser_id(str(event.get_user_id()))

    if force_owner:
        if not is_owner:
            await _help.finish("仅机器人主人可使用此选项")
        return "owner"
    if force_admin:
        if not is_owner:
            await _help.finish("仅机器人主人可切换到管理员视图")
        return "admin"
    if not config.enable_role_views or config.role_view_mode == "manual_only":
        return "owner" if is_owner and config.admin_show_all else "user"
    return "owner" if is_owner else "user"


@_help.handle()
async def _handle_help(
    bot: Bot,
    event: Event,
    plugin_name: Match[tuple[str, ...]],
    show_admin_flag: Match[object],
    show_all_flag: Match[object],
) -> None:
    config = get_help_config()
    prefix = _cmd_prefix()
    role = await _resolve_role(
        event,
        config=config,
        force_admin=show_admin_flag.available,
        force_owner=show_all_flag.available,
    )
    show_all = (
        role == "owner"
        and is_superuser_id(str(event.get_user_id()))
        and (config.admin_show_all or show_all_flag.available)
    )
    target_name = _merge_plugin_name(plugin_name)

    if target_name:
        await _show_detail(
            bot,
            target_name,
            prefix=prefix,
            config=config,
            role=role,
            show_all=show_all,
            matcher=_help,
        )
    else:
        await _show_menu(
            bot,
            prefix=prefix,
            config=config,
            role=role,
            show_all=show_all,
            matcher=_help,
        )


def _merge_plugin_name(m: Match[tuple[str, ...]]) -> str | None:
    if not m.available:
        return None
    parts = [
        item.strip() for item in m.result if isinstance(item, str) and item.strip()
    ]
    return " ".join(parts) if parts else None


# ── plugin metadata ────────────────────────────────────────────────────────


def _cfg(  # noqa: PLR0913
    key: str,
    *,
    label: str = "",
    help_text: str = "",
    order: int = 99,
    fields: list[RegisterConfig] | None = None,
    item_schema: RegisterConfig | None = None,
    choices: list[object] | None = None,
    choice_labels: dict[str, str] | None = None,
) -> RegisterConfig:
    return RegisterConfig(
        key=key,
        default=None,
        type=str,
        label=label,
        help=help_text,
        order=order,
        fields=list(fields or []),
        item_schema=item_schema,
        choices=list(choices or []),
        choice_labels=dict(choice_labels or {}),
    )


_mc = _cfg

__plugin_meta__ = PluginMetadata(
    name="命令帮助",
    description="自动生成命令帮助菜单，支持角色区分和图片渲染",
    usage="发送 /help 查看功能菜单",
    type="application",
    config=HelpConfig,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra=PluginExtraData(
        author="apeiria",
        version="0.1.0",
        plugin_type=PluginType.NORMAL,
        help=HelpExtra(
            category="系统功能",
            introduction="发送 /help 查看功能菜单，支持按插件查看详细命令",
        ),
        ui=UiExtra(order=5),
        commands=["help"],
        config=ConfigExtra(
            fields=[
                _mc(
                    key="appearance",
                    label="外观设置",
                    help_text="帮助菜单的外观配置",
                    order=10,
                    fields=[
                        _mc(key="title", label="标题", order=10, help_text="主标题"),
                        _mc(
                            key="subtitle", label="副标题", order=20, help_text="副标题"
                        ),
                        _mc(
                            key="accent_color",
                            label="强调色",
                            order=30,
                            help_text="主题色",
                        ),
                        _mc(
                            key="expand_commands",
                            label="展开命令",
                            order=40,
                            help_text="是否在主菜单展开命令",
                        ),
                    ],
                ),
                _mc(
                    key="visibility",
                    label="可见性",
                    help_text="控制插件可见性",
                    order=20,
                    fields=[
                        _mc(
                            key="show_builtin_plugins",
                            label="显示内置插件",
                            order=10,
                        ),
                        _mc(key="hidden_plugins", label="隐藏插件列表", order=20),
                    ],
                ),
                _mc(
                    key="roles",
                    label="角色设置",
                    help_text="角色视图配置",
                    order=30,
                    fields=[
                        _mc(key="enabled", label="启用角色视图", order=10),
                        _mc(
                            key="mode",
                            label="角色模式",
                            order=20,
                            choices=["auto", "manual_only"],
                            choice_labels={"auto": "自动", "manual_only": "手动切换"},
                        ),
                        _mc(key="owner_sees_all", label="主人可见全部", order=30),
                        _mc(key="user_title", label="用户视图标题", order=40),
                        _mc(key="admin_title", label="管理员视图标题", order=50),
                        _mc(key="owner_title", label="主人视图标题", order=60),
                    ],
                ),
                _mc(
                    key="assets",
                    label="资源",
                    help_text="静态资源配置",
                    order=40,
                    fields=[
                        _mc(key="banner_image", label="横幅图片", order=10),
                        _mc(key="header_logo", label="Logo图片", order=20),
                        _mc(key="footer_text", label="页脚文本", order=30),
                        _mc(key="font_urls", label="字体URL", order=40),
                        _mc(key="font_family", label="中文字体", order=50),
                        _mc(key="latin_font_family", label="拉丁字体", order=60),
                        _mc(key="mono_font_family", label="等宽字体", order=70),
                    ],
                ),
                _mc(
                    key="render",
                    label="渲染",
                    help_text="渲染相关配置",
                    order=90,
                    fields=[
                        _mc(
                            key="prefer_custom_templates",
                            label="优先自定义模板",
                            order=10,
                        ),
                        _mc(key="disk_cache", label="磁盘缓存", order=20),
                        _mc(key="debug", label="调试模式", order=30),
                    ],
                ),
                _mc(
                    key="plugin_overrides",
                    label="插件覆盖",
                    help_text="覆盖插件显示信息",
                    order=100,
                    item_schema=_mc(
                        key="override",
                        label="覆盖项",
                        help_text="单个插件覆盖配置",
                        fields=[
                            _mc(key="plugin_name", label="插件名", order=10),
                            _mc(key="display_name", label="显示名称", order=20),
                            _mc(key="description", label="描述", order=30),
                            _mc(key="category", label="分类", order=40),
                            _mc(key="order", label="排序", order=50),
                            _mc(key="extra_commands", label="额外命令", order=60),
                        ],
                    ),
                ),
            ]
        ),
        required_plugins=[
            "nonebot_plugin_alconna",
            "nonebot_plugin_htmlrender",
        ],
    ).to_dict(),
)

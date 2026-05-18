"""Help plugin — auto-generated command help system."""

from pathlib import Path

from nonebot import get_driver, require
from nonebot.log import logger
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

from apeiria.builtin_plugins.help.config import (
    HelpConfig,
    get_help_config,
)
from apeiria.builtin_plugins.help.generator import generate_help_list
from apeiria.builtin_plugins.help.renderer import (
    _build_main_menu_data,
    _build_sub_menu_data,
    build_render_cache_key,
    cleanup_stale_disk_cache,
)
from apeiria.i18n import load_locales, t
from apeiria.plugins.metadata.api import (
    ConfigExtra,
    HelpExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)
from apeiria.utils.command_prefix import get_command_prefix

require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
require("apeiria.builtin_plugins.render")

# Register plugin locales
load_locales(Path(__file__).parent / "locales")


def _config_meta(  # noqa: PLR0913
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


def _cleanup_help_disk_cache() -> None:
    config = get_help_config()
    if not config.disk_cache:
        return

    prefix = get_command_prefix()
    valid_keys: set[str] = set()
    for show_all in (False, True):
        for role in ("user", "admin", "owner"):
            plugins = generate_help_list(config, role=role, show_all=show_all)
            template_name = (
                "expanded_menu.html" if config.expand_commands else "main_menu.html"
            )
            main_data = _build_main_menu_data(
                plugins,
                prefix=prefix,
                config=config,
                role=role,
            )
            valid_keys.add(
                build_render_cache_key(
                    template_name,
                    main_data,
                    use_custom_templates=config.custom_templates,
                )
            )
            for plugin in plugins:
                detail_data = _build_sub_menu_data(
                    plugin,
                    prefix=prefix,
                    config=config,
                    role=role,
                )
                valid_keys.add(
                    build_render_cache_key(
                        "sub_menu.html",
                        detail_data,
                        use_custom_templates=config.custom_templates,
                    )
                )

    removed = cleanup_stale_disk_cache(valid_keys)
    if removed > 0:
        logger.info("Removed {} stale help cache file(s)", removed)


__plugin_meta__ = PluginMetadata(
    name=t("help.meta.name"),
    description=t("help.meta.description"),
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage=t("help.meta.usage"),
    type="application",
    config=HelpConfig,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra=PluginExtraData(
        author="apeiria",
        version="0.1.0",
        plugin_type=PluginType.NORMAL,
        help=HelpExtra(
            category=t("help.meta.help_category"),
            introduction=t("help.meta.help_introduction"),
        ),
        ui=UiExtra(order=5),
        commands=["help"],
        config=ConfigExtra(
            fields=[
                _config_meta(
                    key="appearance",
                    label=t("help.config.appearance.label"),
                    order=10,
                    help_text=t("help.config.appearance.help"),
                    fields=[
                        _config_meta(
                            key="title",
                            label=t("help.config.appearance.title.label"),
                            order=10,
                            help_text=t("help.config.appearance.title.help"),
                        ),
                        _config_meta(
                            key="subtitle",
                            label=t("help.config.appearance.subtitle.label"),
                            order=20,
                            help_text=t("help.config.appearance.subtitle.help"),
                        ),
                        _config_meta(
                            key="accent_color",
                            label=t("help.config.appearance.accent_color.label"),
                            order=30,
                            help_text=t("help.config.appearance.accent_color.help"),
                        ),
                        _config_meta(
                            key="expand_commands",
                            label=t("help.config.appearance.expand_commands.label"),
                            order=40,
                            help_text=t("help.config.appearance.expand_commands.help"),
                        ),
                    ],
                ),
                _config_meta(
                    key="visibility",
                    label=t("help.config.visibility.label"),
                    order=20,
                    help_text=t("help.config.visibility.help"),
                    fields=[
                        _config_meta(
                            key="show_builtin_plugins",
                            label=t(
                                "help.config.visibility.show_builtin_plugins.label"
                            ),
                            order=10,
                            help_text=t(
                                "help.config.visibility.show_builtin_plugins.help"
                            ),
                        ),
                        _config_meta(
                            key="hidden_plugins",
                            label=t("help.config.visibility.hidden_plugins.label"),
                            order=20,
                            help_text=t("help.config.visibility.hidden_plugins.help"),
                        ),
                    ],
                ),
                _config_meta(
                    key="roles",
                    label=t("help.config.roles.label"),
                    order=30,
                    help_text=t("help.config.roles.help"),
                    fields=[
                        _config_meta(
                            key="enabled",
                            label=t("help.config.roles.enabled.label"),
                            order=10,
                            help_text=t("help.config.roles.enabled.help"),
                        ),
                        _config_meta(
                            key="mode",
                            label=t("help.config.roles.mode.label"),
                            order=20,
                            help_text=t("help.config.roles.mode.help"),
                            choices=["auto", "manual_only"],
                            choice_labels={
                                "auto": t("help.config.roles.mode.choice_auto"),
                                "manual_only": t(
                                    "help.config.roles.mode.choice_manual_only"
                                ),
                            },
                        ),
                        _config_meta(
                            key="owner_sees_all",
                            label=t("help.config.roles.owner_sees_all.label"),
                            order=30,
                            help_text=t("help.config.roles.owner_sees_all.help"),
                        ),
                        _config_meta(
                            key="user_title",
                            label=t("help.config.roles.user_title.label"),
                            order=40,
                            help_text=t("help.config.roles.user_title.help"),
                        ),
                        _config_meta(
                            key="admin_title",
                            label=t("help.config.roles.admin_title.label"),
                            order=50,
                            help_text=t("help.config.roles.admin_title.help"),
                        ),
                        _config_meta(
                            key="owner_title",
                            label=t("help.config.roles.owner_title.label"),
                            order=60,
                            help_text=t("help.config.roles.owner_title.help"),
                        ),
                    ],
                ),
                _config_meta(
                    key="assets",
                    label=t("help.config.assets.label"),
                    order=40,
                    help_text=t("help.config.assets.help"),
                    fields=[
                        _config_meta(
                            key="banner_image",
                            label=t("help.config.assets.banner_image.label"),
                            order=10,
                            help_text=t("help.config.assets.banner_image.help"),
                        ),
                        _config_meta(
                            key="header_logo",
                            label=t("help.config.assets.header_logo.label"),
                            order=20,
                            help_text=t("help.config.assets.header_logo.help"),
                        ),
                        _config_meta(
                            key="footer_text",
                            label=t("help.config.assets.footer_text.label"),
                            order=30,
                            help_text=t("help.config.assets.footer_text.help"),
                        ),
                        _config_meta(
                            key="font_urls",
                            label=t("help.config.assets.font_urls.label"),
                            order=40,
                            help_text=t("help.config.assets.font_urls.help"),
                        ),
                        _config_meta(
                            key="font_family",
                            label=t("help.config.assets.font_family.label"),
                            order=50,
                            help_text=t("help.config.assets.font_family.help"),
                        ),
                        _config_meta(
                            key="latin_font_family",
                            label=t("help.config.assets.latin_font_family.label"),
                            order=60,
                            help_text=t("help.config.assets.latin_font_family.help"),
                        ),
                        _config_meta(
                            key="mono_font_family",
                            label=t("help.config.assets.mono_font_family.label"),
                            order=70,
                            help_text=t("help.config.assets.mono_font_family.help"),
                        ),
                    ],
                ),
                _config_meta(
                    key="render",
                    label=t("help.config.render.label"),
                    order=90,
                    help_text=t("help.config.render.help"),
                    fields=[
                        _config_meta(
                            key="prefer_custom_templates",
                            label=t("help.config.render.prefer_custom_templates.label"),
                            order=10,
                            help_text=t(
                                "help.config.render.prefer_custom_templates.help"
                            ),
                        ),
                        _config_meta(
                            key="disk_cache",
                            label=t("help.config.render.disk_cache.label"),
                            order=20,
                            help_text=t("help.config.render.disk_cache.help"),
                        ),
                        _config_meta(
                            key="debug",
                            label=t("help.config.render.debug.label"),
                            order=30,
                            help_text=t("help.config.render.debug.help"),
                        ),
                    ],
                ),
                _config_meta(
                    key="plugin_overrides",
                    label=t("help.config.plugin_overrides.label"),
                    order=100,
                    help_text=t("help.config.plugin_overrides.help"),
                    item_schema=_config_meta(
                        key="override",
                        label=t("help.config.plugin_overrides.override.label"),
                        help_text=t("help.config.plugin_overrides.override.help"),
                        fields=[
                            _config_meta(
                                key="plugin_name",
                                label=t(
                                    "help.config.plugin_overrides.override.plugin_name.label"
                                ),
                                order=10,
                                help_text=t(
                                    "help.config.plugin_overrides.override.plugin_name.help"
                                ),
                            ),
                            _config_meta(
                                key="display_name",
                                label=t(
                                    "help.config.plugin_overrides.override.display_name.label"
                                ),
                                order=20,
                                help_text=t(
                                    "help.config.plugin_overrides.override.display_name.help"
                                ),
                            ),
                            _config_meta(
                                key="description",
                                label=t(
                                    "help.config.plugin_overrides.override.description.label"
                                ),
                                order=30,
                                help_text=t(
                                    "help.config.plugin_overrides.override.description.help"
                                ),
                            ),
                            _config_meta(
                                key="category",
                                label=t(
                                    "help.config.plugin_overrides.override.category.label"
                                ),
                                order=40,
                                help_text=t(
                                    "help.config.plugin_overrides.override.category.help"
                                ),
                            ),
                            _config_meta(
                                key="order",
                                label=t(
                                    "help.config.plugin_overrides.override.order.label"
                                ),
                                order=50,
                                help_text=t(
                                    "help.config.plugin_overrides.override.order.help"
                                ),
                            ),
                            _config_meta(
                                key="extra_commands",
                                label=t(
                                    "help.config.plugin_overrides.override.extra_commands.label"
                                ),
                                order=60,
                                help_text=t(
                                    "help.config.plugin_overrides.override.extra_commands.help"
                                ),
                            ),
                        ],
                    ),
                ),
            ]
        ),
        required_plugins=[
            "nonebot_plugin_alconna",
            "nonebot_plugin_localstore",
            "apeiria.builtin_plugins.render",
        ],
    ).to_dict(),
)

from . import help_cmd as help_cmd

get_driver().on_startup(_cleanup_help_disk_cache)

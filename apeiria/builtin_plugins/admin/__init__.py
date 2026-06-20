"""Admin plugin — owner management commands."""

from pathlib import Path

from nonebot import require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

from apeiria.i18n import load_locales, t
from apeiria.plugins.metadata.api import PluginExtraData, PluginType, UiExtra

require("nonebot_plugin_alconna")

# Register plugin locales
load_locales(Path(__file__).parent / "locales")

__plugin_meta__ = PluginMetadata(
    name=t("admin.meta.name"),
    description=t("admin.meta.description"),
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage=t("admin.meta.usage"),
    type="application",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra=PluginExtraData(
        author="apeiria",
        version="0.1.0",
        plugin_type=PluginType.SUPERUSER,
        ui=UiExtra(order=10),
        commands=[
            "status",
            "sid",
            "plugins",
            "plugin",
            "config",
            "access",
            "restart",
        ],
        required_plugins=[
            "nonebot_plugin_alconna",
        ],
    ).to_dict(),
)

from . import access_admin as access_admin
from . import config_view as config_view
from . import plugin_admin as plugin_admin
from . import restart as restart
from . import session_info as session_info
from . import status as status

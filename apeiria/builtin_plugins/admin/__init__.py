from nonebot import require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

from apeiria.plugin.metadata.api import (
    PluginExtraData,
    PluginType,
    UiExtra,
)

require("nonebot_plugin_alconna")

__plugin_meta__ = PluginMetadata(
    name="管理",
    description="超级用户管理命令",
    usage="发送 /admin 查看管理命令",
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
            "access",
            "restart",
        ],
        required_plugins=[
            "nonebot_plugin_alconna",
        ],
    ).to_dict(),
)

from . import access_admin as access_admin
from . import plugin_admin as plugin_admin
from . import restart as restart
from . import session_info as session_info
from . import status as status

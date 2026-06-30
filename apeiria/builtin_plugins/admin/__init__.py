from nonebot import require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")

__plugin_meta__ = PluginMetadata(
    name="管理",
    description="超级用户管理命令",
    usage="发送 /admin 查看管理命令",
    type="application",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
)

from . import access_admin as access_admin
from . import adapter_admin as adapter_admin
from . import plugin_admin as plugin_admin
from . import restart as restart
from . import session_info as session_info
from . import status as status

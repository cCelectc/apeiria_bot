"""Central bot hook registration.

All system-level NoneBot matcher/driver hooks are registered here explicitly,
not via import side effects. Keeps NoneBot decorator usage confined to one
module, making hook wiring ordered and auditable.

Plugin-level lifecycle hooks (web_ui / render / help) continue to live in
their own plugin modules — this registry only owns system-level hooks.
"""

from nonebot import get_driver
from nonebot.message import run_postprocessor, run_preprocessor

from apeiria.bot.hooks.auth import auth_hook
from apeiria.bot.hooks.error import error_hook
from apeiria.bot.hooks.plugin_sync import sync_plugins
from apeiria.bot.hooks.statistics import stats_hook


def register_bot_hooks() -> None:
    """Apply NoneBot hook decorators to system-level hook functions.

    Ordering:
    - Pre-run: auth first (so denied requests short-circuit).
    - Post-run: error + stats (log exceptions, record command stats).
    - Driver startup: plugin_sync fills PluginInfo / PluginPolicyEntry.
    """
    driver = get_driver()

    run_preprocessor(auth_hook)

    run_postprocessor(error_hook)
    run_postprocessor(stats_hook)

    driver.on_startup(sync_plugins)

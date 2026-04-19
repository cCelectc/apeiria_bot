"""Central bot hook registration.

All system-level NoneBot matcher/driver hooks are registered here explicitly,
not via import side effects. This:
- Keeps NoneBot decorator usage confined to one module
- Makes hook wiring ordered and auditable
- Prevents silent annotation-resolution failures at decoration time
  (each hook module just defines a plain `async def` with real imports)

Plugin-level lifecycle hooks (web_ui / render / help) continue to live in
their own plugin modules — this registry only owns system-level hooks.
"""

from nonebot import get_driver
from nonebot.message import run_postprocessor, run_preprocessor

from apeiria.interfaces.bot.hooks.auth import auth_hook
from apeiria.interfaces.bot.hooks.error import error_hook
from apeiria.interfaces.bot.hooks.plugin_sync import sync_plugins
from apeiria.interfaces.bot.hooks.runtime_observe import (
    runtime_observe_post,
    runtime_observe_pre,
)
from apeiria.interfaces.bot.hooks.statistics import stats_hook


def register_bot_hooks() -> None:
    """Apply NoneBot hook decorators to system-level hook functions.

    Ordering:
    - Pre-run: runtime_observe first (build DispatchRequest/frame before auth
      evaluates so diagnostics land on the right request_id), then auth.
    - Post-run: error + stats first (record their diagnostics onto the frame),
      runtime_observe last (seal ExecutionReport with all diagnostics).
    - Driver startup: only plugin_sync is system-level; schema ensure already
      ran synchronously during framework load.
    """
    driver = get_driver()

    run_preprocessor(runtime_observe_pre)
    run_preprocessor(auth_hook)

    run_postprocessor(error_hook)
    run_postprocessor(stats_hook)
    run_postprocessor(runtime_observe_post)

    driver.on_startup(sync_plugins)

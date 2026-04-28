def configure(driver: object) -> None:
    """Project-local startup extension.

    Copy this file to ``user_bot.py`` and edit it freely.
    The repository ignores ``user_bot.py`` so local changes stay out of git.
    Runtime configuration from the Apeiria config root is applied during
    ``nonebot.init(...)`` before this function runs.
    Plugin config declarations are auto-registered from framework and
    enabled plugins before ``nonebot.init(...)`` runs.
    ``pyproject.toml`` is loaded afterwards so native NoneBot plugin
    declarations still work.
    Plugin declarations from ``apeiria.plugins.toml`` in the config root are
    loaded separately.
    Adapter declarations from ``apeiria.adapters.toml`` in the config root are
    registered after this function runs.
    Driver declarations from ``apeiria.drivers.toml`` in the config root are
    applied during ``nonebot.init(...)`` before this function runs.
    """

    _ = driver

    # 1. Attach project-local lifecycle hooks.
    #
    # @driver.on_startup
    # async def _startup() -> None:
    #     from nonebot import logger
    #     logger.info("custom startup hook ready")
    #
    # @driver.on_shutdown
    # async def _shutdown() -> None:
    #     from nonebot import logger
    #     logger.info("custom shutdown hook finished")

    # 2. Register adapters manually if you want to override the default order.
    #
    # from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter
    # driver.register_adapter(OneBotV11Adapter)
    #
    # 3. Put any project-local initialization here.
    #
    # from pathlib import Path
    # data_dir = Path("data") / "custom"
    # data_dir.mkdir(parents=True, exist_ok=True)

    # Keep this function empty until you need local customization.

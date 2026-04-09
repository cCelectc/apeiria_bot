"""Web UI plugin — management dashboard API + static file serving."""

from pathlib import Path

import nonebot
from nonebot import require
from nonebot.log import logger
from nonebot.plugin import PluginMetadata

from apeiria.infra.config.plugins import plugin_config_service
from apeiria.infra.config.webui_config import WebUIConfig
from apeiria.shared.i18n import load_locales, t
from apeiria.shared.plugin_introspection import prewarm_plugin_module_caches
from apeiria.shared.plugin_metadata import (
    ConfigExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)

require("nonebot_plugin_localstore")
require("nonebot_plugin_orm")

load_locales(Path(__file__).parent / "locales")

__plugin_meta__ = PluginMetadata(
    name=t("web_ui.meta.name"),
    description=t("web_ui.meta.description"),
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage=t("web_ui.meta.usage"),
    type="application",
    config=WebUIConfig,
    supported_adapters=None,
    extra=PluginExtraData(
        author="apeiria",
        version="0.1.0",
        plugin_type=PluginType.HIDDEN,
        admin_level=0,
        ui=UiExtra(order=0, hidden=True),
        config=ConfigExtra(
            fields=[
                RegisterConfig(
                    key="token_expire_days",
                    default=7,
                    help=t("web_ui.meta.config_token_expire_days"),
                    type=int,
                )
            ]
        ),
        required_plugins=["nonebot_plugin_localstore", "nonebot_plugin_orm"],
    ).to_dict(),
)

_WEB_DIR = Path(__file__).parent.parent.parent.parent / "web"
_DIST_DIR = _WEB_DIR / "dist"


def _web_ui_url() -> str:
    """Build the current Web UI URL from driver config."""
    import nonebot

    config = nonebot.get_driver().config
    host = str(getattr(config, "host", "127.0.0.1"))
    port = int(getattr(config, "port", 8080))
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"http://{host}:{port}/"


def _mount_routes() -> None:
    """Mount API routes + static frontend into nonebot's ASGI app."""
    import logging

    app = nonebot.get_app()
    from nonebot_plugin_localstore import get_plugin_data_dir

    from apeiria.interfaces.http.routes.router import router

    app.include_router(router, prefix="/api")

    # Redirect uvicorn access logs to file instead of console
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.propagate = False
    log_dir = get_plugin_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "access.log", encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    access_logger.addHandler(file_handler)

    if _DIST_DIR.is_dir():
        from fastapi.staticfiles import StaticFiles
        from starlette.responses import FileResponse

        @app.get("/{path:path}", include_in_schema=False)
        async def _spa_fallback(path: str) -> FileResponse:
            file = _DIST_DIR / path
            if file.is_file():
                return FileResponse(file)
            return FileResponse(_DIST_DIR / "index.html")

        assets_dir = _DIST_DIR / "assets"
        if assets_dir.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=assets_dir),
                name="static",
            )
        logger.info(
            "{}",
            t("web_ui.startup.ready", url=_web_ui_url()),
        )

        from apeiria.infra.webui_auth.secrets import get_secret_file_path

        logger.info(
            "{}",
            t("web_ui.startup.credentials_file", path=get_secret_file_path()),
        )
    else:
        logger.warning("{}", t("web_ui.startup.build_disabled"))
        logger.debug("Web UI frontend assets not found in {}", _DIST_DIR)


def _warm_plugin_management_caches() -> None:
    """Warm plugin-management caches during Web UI startup."""
    configured_modules = set(
        plugin_config_service.read_project_plugin_config()["modules"]
    )
    loaded_modules = {
        plugin.module_name
        for plugin in nonebot.get_loaded_plugins()
        if getattr(plugin, "module_name", None)
    }
    candidate_modules = configured_modules | loaded_modules
    if not candidate_modules:
        return

    prewarm_plugin_module_caches(candidate_modules)
    logger.debug(
        "Plugin management caches warmed for {} modules",
        len(candidate_modules),
    )


from nonebot import get_driver

get_driver().on_startup(_mount_routes)
get_driver().on_startup(_warm_plugin_management_caches)

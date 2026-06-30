from __future__ import annotations

import os
import sys
from pathlib import Path

from nonebot.log import logger


def _browsers_registry_dir() -> Path | None:
    override = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if override == "0":
        try:
            import playwright
        except ImportError:
            return None
        return (
            Path(playwright.__file__).parent / "driver" / "package" / ".local-browsers"
        )
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "ms-playwright"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    return Path.home() / ".cache" / "ms-playwright"


def _chromium_installed() -> bool:
    registry = _browsers_registry_dir()
    if registry is None or not registry.is_dir():
        return False
    return any(
        entry.is_dir()
        and entry.name.startswith("chromium")
        and (entry / "INSTALLATION_COMPLETE").exists()
        for entry in registry.iterdir()
    )


def ensure_render_ready() -> bool:
    """启动预检：Playwright chromium 未就绪时把 RENDER_STARTUP_MODE 降级为 off。

    必须在 ``nonebot.init()`` 之前调用。仅当 ``RENDER_BACKEND=playwright`` 时生效，
    且只读注册目录、不拉起 node driver / 浏览器。

    Returns:
        渲染环境是否就绪。
    """
    if os.environ.get("RENDER_BACKEND") != "playwright":
        return True
    if _chromium_installed():
        return True
    os.environ["RENDER_STARTUP_MODE"] = "off"
    logger.warning(
        "Playwright chromium not found; RENDER_STARTUP_MODE downgraded to 'off'. "
        "Run 'playwright install chromium' to enable image rendering "
        "(text fallback stays active)."
    )
    return False

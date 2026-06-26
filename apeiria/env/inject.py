from __future__ import annotations

import site
from pathlib import Path

from nonebot.log import logger

_injected: set[str] = set()


def _resolve_site_packages(venv_path: Path) -> Path | None:
    for lib_dir in sorted(venv_path.glob("lib/python*/site-packages")):
        return lib_dir
    return None


def inject_apeiria_paths() -> None:
    venv_path = Path(".apeiria/.venv")
    if not venv_path.exists():
        logger.warning("Plugin venv not found at {}. Run sync first.", venv_path)
        return

    sp = _resolve_site_packages(venv_path)
    if sp is None:
        logger.warning("Plugin site-packages not found")
        return

    site_packages_str = str(sp.resolve())
    if site_packages_str in _injected:
        return

    site.addsitedir(site_packages_str)
    _injected.add(site_packages_str)
    logger.info("Injected plugin path: {}", site_packages_str)

    import nonebot

    pyproject = Path(".apeiria/pyproject.toml")
    if pyproject.exists():
        nonebot.load_from_toml(str(pyproject))

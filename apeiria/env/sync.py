from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from nonebot.log import logger


def _find_uv() -> str | None:
    uv = shutil.which("uv")
    if uv is not None:
        return uv
    home = Path.home() / ".cargo" / "bin" / "uv"
    if home.exists():
        return str(home)
    return None


def sync_apeiria_env() -> bool:
    uv = _find_uv()
    if uv is None:
        logger.error("uv not found — install uv first: https://docs.astral.sh/uv/")
        return False

    result = subprocess.run(
        [uv, "sync", "--directory", ".apeiria"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        logger.error(
            "uv sync failed: {}", result.stderr.strip() or result.stdout.strip()
        )
        return False
    logger.success("Plugin environment synced")
    return True

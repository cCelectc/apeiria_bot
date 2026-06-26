from __future__ import annotations

from pathlib import Path

import nonebot
from nonebot.log import logger

from apeiria.access.control import AccessControl
from apeiria.env.ensure import ensure_apeiria_env
from apeiria.env.inject import inject_apeiria_paths
from apeiria.env.sync import sync_apeiria_env
from apeiria.plugin.scanner import BUILTIN_LIST, _is_enabled, _load_plugins_yaml

_access_control: AccessControl | None = None


def get_access_control() -> AccessControl:
    if _access_control is None:
        raise RuntimeError("Access control not initialized")  # noqa: TRY003
    return _access_control


def step_db_migrate() -> None:
    from alembic.config import Config

    from alembic import command

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    logger.success("Database migrations applied")


def step_apeiria_ensure() -> None:
    ensure_apeiria_env()
    logger.success("Plugin environment ensured")


def step_apeiria_sync() -> None:
    if sync_apeiria_env():
        logger.success("Plugin environment synced")


def step_apeiria_inject() -> None:
    inject_apeiria_paths()


def step_load_builtins() -> None:
    data = _load_plugins_yaml()
    for name in BUILTIN_LIST:
        if _is_enabled(name, data):
            module = f"apeiria.builtin_plugins.{name}"
            nonebot.load_plugin(module)
            logger.debug("Loaded builtin plugin: {}", name)
        else:
            logger.debug("Skipped disabled builtin plugin: {}", name)


def step_load_local() -> None:
    data = _load_plugins_yaml()
    plugins_dir = Path(".apeiria/plugins")
    if not plugins_dir.is_dir():
        return
    for entry in sorted(plugins_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        if not (entry / "__init__.py").is_file():
            continue
        name = entry.name
        if _is_enabled(name, data):
            nonebot.load_plugin(str(entry.resolve()))
            logger.debug("Loaded local plugin: {}", name)
        else:
            logger.debug("Skipped disabled local plugin: {}", name)


def step_load_pypi() -> None:
    pyproject = Path(".apeiria/pyproject.toml")
    if not pyproject.exists():
        return

    data = _load_plugins_yaml()
    raw = pyproject.read_text(encoding="utf-8")
    enabled_entries: dict[str, str] = {}
    in_plugins = False
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped == "[tool.nonebot.plugins]":
            in_plugins = True
            continue
        if in_plugins:
            if stripped.startswith("["):
                break
            if "=" in stripped:
                key, val = stripped.split("=", 1)
                key = key.strip().strip('"')
                if _is_enabled(key, data):
                    enabled_entries[key] = val.strip()

    if not enabled_entries:
        return

    temp_path = Path("data/.runtime_plugins.toml")
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[tool.nonebot.plugins]"]
    for key, val in enabled_entries.items():
        lines.append(f'"{key}" = {val}')
    temp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    nonebot.load_from_toml(str(temp_path))
    logger.success("Loaded PyPI plugins via temporary config")


def step_conversation() -> None:
    from apeiria.conversation.store import append_message

    @nonebot.on_message(None, block=False)  # pyright: ignore[reportCallIssue]
    async def _persist_inbound(event: nonebot.adapters.Event) -> None:  # pyright: ignore[reportAttributeAccessIssue]
        try:
            session_id = event.get_session_id()
            user_id = event.get_user_id()
            text = event.get_plaintext()
            await append_message(
                session_id=session_id or "unknown",
                role="user",
                content=text,
                user_id=user_id,
            )
        except Exception:  # noqa: BLE001
            logger.opt(exception=True).debug("Failed to persist inbound message")

    logger.success("Message persistence hook installed")


def step_access() -> None:
    global _access_control  # noqa: PLW0603
    _access_control = AccessControl()

    @nonebot.get_driver().on_startup
    async def _load_rules() -> None:
        assert _access_control is not None
        await _access_control.load_snapshot()

    @nonebot.get_driver().on_bot_connect
    async def _reload_rules(bot: nonebot.adapters.Bot) -> None:  # noqa: ARG001  # pyright: ignore[reportAttributeAccessIssue]
        assert _access_control is not None
        await _access_control.load_snapshot()

    logger.success("Access control initialized")


def step_web() -> None:
    from fastapi import FastAPI  # noqa: TC002

    from apeiria.web.routes import router

    driver = nonebot.get_driver()
    raw_app = getattr(driver, "server_app", None) or getattr(driver, "asgi", None)
    if raw_app is None:
        logger.warning("Web app not available — driver does not support ASGI")
        return
    app: FastAPI = raw_app
    app.include_router(router)
    logger.success("Web UI routes registered")

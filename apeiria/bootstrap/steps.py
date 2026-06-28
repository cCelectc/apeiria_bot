from __future__ import annotations

from pathlib import Path

import nonebot
from nonebot.log import logger
from nonebot.rule import Rule

from apeiria.access.control import AccessControl
from apeiria.env.ensure import ensure_apeiria_env
from apeiria.env.inject import inject_apeiria_paths
from apeiria.env.sync import sync_apeiria_env
from apeiria.plugin.scanner import (
    BUILTIN_LIST,
    _is_enabled,
    _load_plugins_yaml,
    manifest_module_candidate,
    scan_plugins,
)

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


def _read_adapter_states() -> dict[str, dict]:
    import yaml

    yaml_path = Path(".apeiria/adapters.yaml")
    if not yaml_path.exists():
        return {}
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    return data.get("states") or {}


def step_load_builtin_adapters() -> None:
    from apeiria.config.loader import load_adapters_from_toml

    states = _read_adapter_states()
    load_adapters_from_toml("pyproject.toml", states=states)


def step_load_adapters() -> None:
    from apeiria.config.loader import load_adapters_from_toml

    states = _read_adapter_states()
    load_adapters_from_toml(".apeiria/pyproject.toml", states=states)


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
    loaded = 0
    for manifest in scan_plugins():
        if manifest.source != "pypi":
            continue
        if not manifest.enabled:
            logger.debug("Skipped disabled PyPI plugin: {}", manifest.name)
            continue
        module = manifest_module_candidate(manifest)
        if not module:
            continue
        try:
            nonebot.load_plugin(module)
        except Exception:  # noqa: BLE001
            logger.opt(exception=True).warning(
                "Failed to load PyPI plugin: {} ({})", manifest.name, module
            )
            continue
        loaded += 1
        logger.debug("Loaded PyPI plugin: {} ({})", manifest.name, module)

    if loaded:
        logger.success("Loaded {} PyPI plugin(s)", loaded)


_conversation_handler = nonebot.on_message(Rule(), block=False)


@_conversation_handler.handle()
async def _persist_inbound(event: nonebot.adapters.Event) -> None:  # pyright: ignore[reportAttributeAccessIssue]
    from apeiria.conversation.store import append_message

    try:
        session_id = event.get_session_id()
        if session_id and session_id.startswith("webchat:"):
            return
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


def step_conversation() -> None:
    logger.success("Message persistence hook installed")


def step_access() -> None:
    global _access_control  # noqa: PLW0603
    _access_control = AccessControl()

    from apeiria.access.hook import install_access_hook

    install_access_hook()

    @nonebot.get_driver().on_startup
    async def _load_rules() -> None:
        assert _access_control is not None
        await _access_control.load_snapshot()

    @nonebot.get_driver().on_bot_connect
    async def _reload_rules(bot: nonebot.adapters.Bot) -> None:  # noqa: ARG001  # pyright: ignore[reportAttributeAccessIssue]
        assert _access_control is not None
        await _access_control.load_snapshot()

    logger.success("Access control initialized")


def _source_fingerprint(src_dir: Path) -> str:
    import hashlib

    hasher = hashlib.sha256()
    for f in sorted(src_dir.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix not in (".vue", ".ts", ".js", ".css", ".json", ".html"):
            continue
        hasher.update(str(f.relative_to(src_dir)).encode())
        hasher.update(f.read_bytes())
    return hasher.hexdigest()


def _needs_frontend_build(dist_dir: Path) -> bool:
    index = dist_dir / "index.html"
    if not index.is_file():
        return True

    src_dir = Path("webui/src")
    if not src_dir.is_dir():
        return False

    current = _source_fingerprint(src_dir)
    fingerprint_file = dist_dir / ".build_fingerprint"
    try:
        stored = fingerprint_file.read_text().strip()
    except (OSError, ValueError):
        return True
    return stored != current


def _try_auto_build_frontend() -> None:
    import shutil
    import subprocess

    if not shutil.which("pnpm") or not shutil.which("node"):
        logger.debug("pnpm/node not available, skipping frontend auto-build")
        return

    frontend_dir = Path("webui")
    dist_dir = frontend_dir / "dist"

    if not _needs_frontend_build(dist_dir):
        return

    logger.info("Frontend build needed — running pnpm build in webui/ ...")
    try:
        subprocess.run(
            ["pnpm", "install", "--frozen-lockfile"],
            cwd=str(frontend_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        result = subprocess.run(
            ["pnpm", "build"],
            cwd=str(frontend_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            logger.warning("Frontend build failed:\n{}", result.stderr[-500:])
        else:
            logger.success("Frontend build completed")
    except OSError as e:
        logger.warning("Failed to run frontend build: {}", e)


def step_web() -> None:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse

    from apeiria.config.loader import load_config
    from apeiria.web.auth import auth_router, ensure_credentials
    from apeiria.web.logs import (
        get_log_hub,
        logs_router,
        route_access_logs,
    )
    from apeiria.web.routes import router

    driver = nonebot.get_driver()
    raw_app = getattr(driver, "server_app", None) or getattr(driver, "asgi", None)
    if raw_app is None:
        logger.warning("Web app not available — driver does not support ASGI")
        return
    app: FastAPI = raw_app

    app_config = load_config("data/config.yaml")
    ensure_credentials()
    get_log_hub().install_sinks(app_config.apeiria.logging)
    route_access_logs(app_config.apeiria.logging)

    app.include_router(auth_router)
    app.include_router(logs_router)
    app.include_router(router)

    frontend_dir = Path("webui/dist")

    _try_auto_build_frontend()

    @app.get("/{full_path:path}")
    async def _serve_frontend(full_path: str) -> FileResponse:
        if not frontend_dir.exists():
            raise HTTPException(status_code=404, detail="Frontend not built")
        candidate = frontend_dir / full_path
        if not candidate.exists() or not candidate.is_file():
            candidate = frontend_dir / "index.html"
        if not candidate.exists():
            raise HTTPException(status_code=404, detail="Frontend not built")
        return FileResponse(str(candidate))

    logger.success("Web UI routes registered")

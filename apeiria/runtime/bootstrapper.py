from __future__ import annotations

from pathlib import Path

from nonebot.log import logger


def _step_environment() -> None:
    logger.debug("Step 1/8 Environment")
    try:
        from apeiria.environment.extension_project import (
            ensure_plugin_project,
            inject_plugin_site_packages,
            process_pending_plugin_module_uninstalls,
            process_pending_plugin_requirement_removals,
        )

        ensure_plugin_project()
        process_pending_plugin_requirement_removals()
        process_pending_plugin_module_uninstalls()
        inject_plugin_site_packages()
    except ImportError:
        logger.debug("Extension project module not available, skipping")

    try:
        from apeiria.plugins.config_bootstrap import bootstrap_plugin_configs

        bootstrap_plugin_configs()
    except ImportError:
        logger.debug("Plugin config bootstrap not available, skipping")


def _step_config() -> dict:
    logger.debug("Step 2/8 Config")
    from apeiria.config.loader import load_startup_kwargs

    return load_startup_kwargs()


def _init_database_sync() -> None:
    """Initialise the async DB engine synchronously (before event loop)."""
    from apeiria.db.engine import init_engine
    from apeiria.db.runtime import database_runtime

    database_runtime.ensure_ready()
    import asyncio

    asyncio.run(init_engine(database_runtime.database_path()))


async def _step_database_async() -> None:
    """Post-startup DB work: settings row, FAISS, embedding model preload."""
    logger.debug("Step 3/8 Database")
    from sqlalchemy import select

    from apeiria.db.base import _now_iso
    from apeiria.db.engine import get_session
    from apeiria.db.models.ai_settings import AIRuntimeSettings

    async with get_session() as db:
        existing = (
            await db.execute(select(AIRuntimeSettings).where(AIRuntimeSettings.id == 1))
        ).scalar_one_or_none()
        if not existing:
            db.add(AIRuntimeSettings(id=1, updated_at=_now_iso()))
            await db.commit()
            logger.debug("Created default ai_runtime_settings row")

    try:
        from apeiria.ai.memory.service import _get_facts_index

        _get_facts_index()
        from apeiria.ai.knowledge.service import _get_knowledge_index

        _get_knowledge_index()
    except Exception:  # noqa: BLE001
        logger.debug("FAISS index pre-load skipped", exc_info=True)

    try:
        from apeiria.ai.model.adapters.fastembed_adapter import (
            FastEmbedProvider,
        )

        provider = FastEmbedProvider()
        provider._ensure_model()
        logger.debug("Default embedding model ready")
    except Exception:  # noqa: BLE001
        logger.debug("FastEmbed pre-download skipped", exc_info=True)

    async with get_session() as db:
        settings = (
            await db.execute(select(AIRuntimeSettings).where(AIRuntimeSettings.id == 1))
        ).scalar_one_or_none()
        if settings and not settings.default_chat_model:
            logger.warning(
                "default_chat_model is not set. AI processing will be skipped."
            )


def _step_prepare_sync() -> None:
    """Register context handlers, import builtin tools, load skills (sync)."""
    logger.debug("Step 4/8 Prepare (sync)")
    from apeiria.ai.knowledge.handler import knowledge_context_handler
    from apeiria.ai.memory.handler import memory_context_handler
    from apeiria.ai.persona.handler import persona_context_handler
    from apeiria.ai.relationship.handler import (
        relationship_context_handler,
    )
    from apeiria.ai.skills.handler import skills_context_handler
    from apeiria.ai.tools.registry import register_context_handler

    register_context_handler(persona_context_handler)
    register_context_handler(relationship_context_handler)
    register_context_handler(memory_context_handler)
    register_context_handler(knowledge_context_handler)
    register_context_handler(skills_context_handler)

    import apeiria.ai.tools.builtin  # noqa: F401

    try:
        from apeiria.ai.skills.catalog import load_skills

        skills_dirs = [Path("skills"), Path(".apeiria/skills")]
        load_skills(skills_dirs)
    except Exception:  # noqa: BLE001
        logger.debug("Skills loading skipped", exc_info=True)


async def _step_prepare_async() -> None:
    """MCP / ACP connections (needs running event loop)."""
    logger.debug("Step 4/8 Prepare (async)")
    try:
        from apeiria.ai.mcp.registry import connect_all

        count = await connect_all()
        if count:
            logger.info("MCP: {} tools registered", count)
    except Exception:  # noqa: BLE001
        logger.warning("MCP connection failed", exc_info=True)

    try:
        from apeiria.ai.acp.registry import register_acp_tools

        count = await register_acp_tools()
        if count:
            logger.info("ACP: {} agent tools registered", count)
    except Exception:  # noqa: BLE001
        logger.warning("ACP registration failed", exc_info=True)


def _step_user_extensions() -> None:
    logger.debug("Step 5/8 User extensions")
    user_bot = Path("user_bot.py")
    if user_bot.exists():
        import importlib.util

        spec = importlib.util.spec_from_file_location("user_bot", user_bot)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            logger.debug("Loaded user_bot.py")


def _step_framework() -> None:
    logger.debug("Step 6/8 Framework (builtin plugins)")
    import logging

    import nonebot
    from nonebot.log import logger as nb_logger

    # Suppress duplicate uvicorn log lines (root logger already bridges to loguru)
    for logger_name in ("uvicorn.error", "uvicorn"):
        logging.getLogger(logger_name).propagate = False

    from apeiria._framework_loader import (
        BUILTIN_APPLICATION_PLUGIN_MODULES,
        FRAMEWORK_PLUGIN_MODULES,
    )
    from apeiria.db.engine import close_engine

    for plugin in FRAMEWORK_PLUGIN_MODULES:
        nonebot.load_plugin(plugin)

    try:
        from apeiria.plugins.state import get_disabled_plugin_modules_sync

        disabled = get_disabled_plugin_modules_sync(BUILTIN_APPLICATION_PLUGIN_MODULES)
    except (ImportError, RuntimeError, OSError):
        disabled = set()

    for plugin in BUILTIN_APPLICATION_PLUGIN_MODULES:
        if plugin in disabled:
            nb_logger.info("Skip disabled builtin plugin {}", plugin)
            continue
        nonebot.load_plugin(plugin)

    nonebot.load_plugin("apeiria.builtin_plugins.message_persist")

    try:
        from apeiria.bot.hooks.registry import register_bot_hooks

        register_bot_hooks()
    except ImportError:
        logger.debug("Bot hooks not available", exc_info=True)

    driver = nonebot.get_driver()

    @driver.on_shutdown
    async def _close_async_engine() -> None:
        await close_engine()


def _step_user_plugins(startup_kwargs: dict) -> None:
    logger.debug("Step 7/8 User plugins")
    import nonebot

    plugins = startup_kwargs.get("_plugins", [])
    for plugin in plugins:
        try:
            nonebot.load_plugin(plugin)
        except Exception:  # noqa: PERF203
            logger.exception("Failed to load plugin: {}", plugin)
            raise

    plugin_dirs = startup_kwargs.get("_plugin_dirs", [])
    for d in plugin_dirs:
        if d:
            nonebot.load_plugins(d)


async def _step_start() -> None:
    logger.debug("Step 8/8 Start")
    try:
        from nonebot_plugin_apscheduler import scheduler

        from apeiria.builtin_plugins.ai import get_rhythm_manager

        rhythm = get_rhythm_manager()
        if rhythm:
            scheduler.add_job(
                rhythm.tick_all,
                "interval",
                seconds=15,
                id="rhythm_tick",
            )
    except Exception:  # noqa: BLE001
        logger.debug("Scheduler setup skipped", exc_info=True)


def _init_runtime_context() -> None:
    from pathlib import Path

    from apeiria.access.management import access_management_service
    from apeiria.config.project import project_config_service
    from apeiria.conversation.service import ensure_session as _conv_ensure
    from apeiria.db.runtime import database_runtime
    from apeiria.environment.manager import environment_service
    from apeiria.plugins.catalog import plugin_governance_service
    from apeiria.plugins.management import plugin_management_service
    from apeiria.runtime.context import ApeiriaRuntime, set_current_runtime
    from apeiria.runtime.control_plane import ApeiriaControlPlane
    from apeiria.system.management import system_management_service
    from apeiria.system.project_update import project_update_service
    from apeiria.webchat.service import web_chat_service

    project_root = Path.cwd()
    runtime = ApeiriaRuntime(
        project_root=project_root,
        config=project_config_service,
        environment=environment_service,
        database=database_runtime,
        conversation=_conv_ensure,  # type: ignore[arg-type]
        chat=web_chat_service,
        plugins=plugin_governance_service,
        plugin_management=plugin_management_service,
        access=access_management_service,
        system=system_management_service,
        project_update=project_update_service,
    )
    runtime.control_plane = ApeiriaControlPlane(runtime)
    set_current_runtime(runtime)
    logger.debug("ApeiriaRuntime initialized with control plane")


def _load_adapters(adapter_modules: list[str]) -> None:
    if not adapter_modules:
        return
    import importlib

    import nonebot

    driver = nonebot.get_driver()
    for module_path in adapter_modules:
        try:
            mod = importlib.import_module(module_path)
            adapter_cls = getattr(mod, "Adapter", None)
            if adapter_cls is not None:
                driver.register_adapter(adapter_cls)
                logger.debug("Registered adapter: {}", module_path)
            else:
                logger.warning("No Adapter class in {}", module_path)
        except (ImportError, AttributeError):  # noqa: PERF203
            logger.warning("Failed to load adapter: {}", module_path, exc_info=True)


class ApeiriaBootstrapper:
    def run(self) -> None:
        import nonebot

        logger.debug("Apeiria bootstrap starting (8 steps)")

        _step_environment()
        startup_kwargs = _step_config()

        nonebot.init(
            **{k: v for k, v in startup_kwargs.items() if not k.startswith("_")}
        )

        _load_adapters(startup_kwargs.get("_adapter_modules", []))

        _init_database_sync()
        _step_prepare_sync()
        _step_user_extensions()
        _step_framework()
        _step_user_plugins(startup_kwargs)

        driver = nonebot.get_driver()

        @driver.on_startup
        async def _async_init() -> None:
            await _step_database_async()
            await _step_prepare_async()
            _init_runtime_context()
            await _step_start()
            logger.debug("Apeiria bootstrap complete")

        nonebot.run()

    def initialize_nonebot(self) -> None:
        import nonebot

        _step_environment()
        startup_kwargs = _step_config()
        nonebot.init(
            **{k: v for k, v in startup_kwargs.items() if not k.startswith("_")}
        )

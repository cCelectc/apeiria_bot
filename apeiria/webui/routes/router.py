"""Core HTTP router aggregation."""

from fastapi import APIRouter

from apeiria.webui.routes.access import router as access_router
from apeiria.webui.routes.adapters import router as adapters_router
from apeiria.webui.routes.ai.agents import router as ai_agents_router
from apeiria.webui.routes.ai.knowledge import router as ai_knowledge_router
from apeiria.webui.routes.ai.mcp_servers import router as ai_mcp_router
from apeiria.webui.routes.ai.memories import router as ai_memories_router
from apeiria.webui.routes.ai.models import router as ai_models_router
from apeiria.webui.routes.ai.personas import router as ai_personas_router
from apeiria.webui.routes.ai.profiles import router as ai_profiles_router
from apeiria.webui.routes.ai.relationships import router as ai_relationships_router
from apeiria.webui.routes.ai.sessions import router as ai_sessions_router
from apeiria.webui.routes.ai.settings import router as ai_settings_router
from apeiria.webui.routes.ai.skills import router as ai_skills_router
from apeiria.webui.routes.ai.tools import router as ai_tools_router
from apeiria.webui.routes.auth import router as auth_router
from apeiria.webui.routes.chat import router as chat_router
from apeiria.webui.routes.core import router as core_router
from apeiria.webui.routes.dashboard import router as dashboard_router
from apeiria.webui.routes.drivers import router as driver_config_router
from apeiria.webui.routes.logs import router as log_router
from apeiria.webui.routes.plugins import router as plugins_router
from apeiria.webui.routes.update import router as project_update_router

router = APIRouter()

# Auth
router.include_router(auth_router, prefix="/auth", tags=["auth"])

# Dashboard
router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])

# Core config
router.include_router(core_router, prefix="/core", tags=["core"])

# Driver config
router.include_router(driver_config_router, prefix="/drivers", tags=["drivers"])

# Adapters (config, selection, store)
router.include_router(adapters_router, prefix="/adapters", tags=["adapters"])

# Plugins (catalog, config, management, store)
router.include_router(plugins_router, prefix="/plugins", tags=["plugins"])

# Permissions
router.include_router(access_router, prefix="/permissions", tags=["permissions"])

# Logs
router.include_router(log_router, prefix="/logs", tags=["logs"])

# Chat
router.include_router(chat_router, prefix="/chat", tags=["chat"])

# Project update
router.include_router(project_update_router, prefix="/update", tags=["update"])

# AI
router.include_router(ai_settings_router, prefix="/ai/settings", tags=["ai-settings"])
router.include_router(ai_agents_router, prefix="/ai/agents", tags=["ai-agents"])
router.include_router(ai_mcp_router, prefix="/ai/mcp/servers", tags=["ai-mcp"])
router.include_router(ai_personas_router, prefix="/ai/personas", tags=["ai-personas"])
router.include_router(ai_profiles_router, prefix="/ai/profiles", tags=["ai-profiles"])
router.include_router(
    ai_relationships_router, prefix="/ai/relationships", tags=["ai-relationships"]
)
router.include_router(ai_memories_router, prefix="/ai/memories", tags=["ai-memories"])
router.include_router(
    ai_knowledge_router, prefix="/ai/knowledge", tags=["ai-knowledge"]
)
router.include_router(ai_models_router, prefix="/ai/models", tags=["ai-models"])
router.include_router(ai_sessions_router, prefix="/ai/sessions", tags=["ai-sessions"])
router.include_router(ai_tools_router, prefix="/ai/tools", tags=["ai-tools"])
router.include_router(ai_skills_router, prefix="/ai/skills", tags=["ai-skills"])

__all__ = ["router"]

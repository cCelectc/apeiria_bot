"""AI capability — library interface for other plugins and the Apeiria host.

Import stable paths from here; the :mod:`apeiria.builtin_plugins.ai` plugin
owns the NoneBot-facing lifecycle (message handler, Web UI route
registration), but the underlying capability is exposed as a regular library.

Runtime singletons (``ai_service``, ``model_gateway``, ``tool_gateway``, the
per-domain services) expect the AI plugin to be loaded — disabling the AI
plugin is allowed, but invoking these from other plugins afterwards may fail
or no-op. Declare ``required_plugins=["apeiria.builtin_plugins.ai"]`` in your
plugin metadata to enforce the dependency.
"""

from apeiria.ai.conversation.service import chat_session_service
from apeiria.ai.future_task.service import ai_future_task_service
from apeiria.ai.memory.service import ai_memory_service
from apeiria.ai.model.gateway import model_gateway
from apeiria.ai.person.service import ai_person_profile_service
from apeiria.ai.persona.service import ai_persona_service
from apeiria.ai.relationship.service import ai_relationship_service
from apeiria.ai.reply_strategy.service import reply_strategy_service
from apeiria.ai.retention import ai_retention_service
from apeiria.ai.service import AIService, AIServiceStatus, ai_service
from apeiria.ai.skills.service import ai_skill_service
from apeiria.ai.tools.gateway import tool_gateway
from apeiria.ai.tools.service import ai_tool_service

__all__ = [
    "AIService",
    "AIServiceStatus",
    "ai_future_task_service",
    "ai_memory_service",
    "ai_person_profile_service",
    "ai_persona_service",
    "ai_relationship_service",
    "ai_retention_service",
    "ai_service",
    "ai_skill_service",
    "ai_tool_service",
    "chat_session_service",
    "model_gateway",
    "reply_strategy_service",
    "tool_gateway",
]

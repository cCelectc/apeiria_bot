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

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apeiria.ai.memory import ai_memory_service
    from apeiria.ai.model import model_gateway
    from apeiria.ai.person import ai_person_profile_service
    from apeiria.ai.persona import ai_persona_service
    from apeiria.ai.relationship import ai_relationship_service
    from apeiria.ai.retention import ai_retention_service
    from apeiria.ai.service import AIService, AIServiceStatus, ai_service
    from apeiria.ai.skills import ai_skill_service
    from apeiria.ai.tools import ai_tool_service, tool_gateway

__all__ = [
    "AIService",
    "AIServiceStatus",
    "ai_memory_service",
    "ai_person_profile_service",
    "ai_persona_service",
    "ai_relationship_service",
    "ai_retention_service",
    "ai_service",
    "ai_skill_service",
    "ai_tool_service",
    "model_gateway",
    "tool_gateway",
]

_LAZY_MODULES = {
    "AIService": "apeiria.ai.service",
    "AIServiceStatus": "apeiria.ai.service",
    "ai_memory_service": "apeiria.ai.memory",
    "ai_person_profile_service": "apeiria.ai.person",
    "ai_persona_service": "apeiria.ai.persona",
    "ai_relationship_service": "apeiria.ai.relationship",
    "ai_retention_service": "apeiria.ai.retention",
    "ai_service": "apeiria.ai.service",
    "ai_skill_service": "apeiria.ai.skills",
    "ai_tool_service": "apeiria.ai.tools",
    "model_gateway": "apeiria.ai.model",
    "tool_gateway": "apeiria.ai.tools",
}


def __getattr__(name: str) -> Any:
    module_path = _LAZY_MODULES.get(name)
    if module_path is not None:
        module = import_module(module_path)
        return getattr(module, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)

"""AI foundation primitives for plugins and the Apeiria host.

Import stable paths from here; the :mod:`apeiria.builtin_plugins.ai` plugin
owns the NoneBot-facing lifecycle (message handler, Web UI route
registration), while provider-neutral capability contracts live in
:mod:`apeiria.ai.capabilities`.

Application orchestration and readiness live under :mod:`apeiria.app.ai`.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apeiria.ai.memory import ai_memory_service
    from apeiria.ai.person import ai_person_profile_service
    from apeiria.ai.persona import ai_persona_service
    from apeiria.ai.relationship import ai_relationship_service
    from apeiria.ai.retention import ai_retention_service
    from apeiria.ai.skills import ai_skill_service
    from apeiria.ai.tools import ai_tool_service

__all__ = [
    "ai_memory_service",
    "ai_person_profile_service",
    "ai_persona_service",
    "ai_relationship_service",
    "ai_retention_service",
    "ai_skill_service",
    "ai_tool_service",
]

_LAZY_MODULES = {
    "ai_memory_service": "apeiria.ai.memory",
    "ai_person_profile_service": "apeiria.ai.person",
    "ai_persona_service": "apeiria.ai.persona",
    "ai_relationship_service": "apeiria.ai.relationship",
    "ai_retention_service": "apeiria.ai.retention",
    "ai_skill_service": "apeiria.ai.skills",
    "ai_tool_service": "apeiria.ai.tools",
}


def __getattr__(name: str) -> Any:
    module_path = _LAZY_MODULES.get(name)
    if module_path is not None:
        module = import_module(module_path)
        return getattr(module, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)

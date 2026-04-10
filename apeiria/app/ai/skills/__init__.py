"""Skill boundary exports with lazy runtime/service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .catalog import AISkillContract, AISkillDefinition
from .debug import (
    AICapabilityDefinition,
    AICapabilityPreview,
    AISkillExecutionView,
)
from .models import AIToolPolicy, AIToolSpec

if TYPE_CHECKING:
    from .bridge import (
        AINoneBotSkillBridge,
        SkillNotAllowedError,
        SkillPolicyDeniedError,
        invoke_skill_with_policy,
    )
    from .service import AISkillRuntimeRequest, AISkillRuntimeResult, ai_skill_service

__all__ = [
    "AICapabilityDefinition",
    "AICapabilityPreview",
    "AINoneBotSkillBridge",
    "AISkillContract",
    "AISkillDefinition",
    "AISkillExecutionView",
    "AISkillRuntimeRequest",
    "AISkillRuntimeResult",
    "AIToolPolicy",
    "AIToolSpec",
    "SkillNotAllowedError",
    "SkillPolicyDeniedError",
    "ai_skill_service",
    "invoke_skill_with_policy",
]

_LAZY_EXPORTS = {
    "AINoneBotSkillBridge": ".bridge",
    "SkillNotAllowedError": ".bridge",
    "SkillPolicyDeniedError": ".bridge",
    "invoke_skill_with_policy": ".bridge",
    "AISkillRuntimeRequest": ".service",
    "AISkillRuntimeResult": ".service",
    "ai_skill_service": ".service",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value

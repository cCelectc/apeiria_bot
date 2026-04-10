"""Skill-facing compatibility boundary over the legacy tools domain."""

from .bridge import (
    AINoneBotSkillBridge,
    SkillNotAllowedError,
    SkillPolicyDeniedError,
    invoke_skill_with_policy,
)
from .catalog import AISkillContract, AISkillDefinition
from .debug import (
    AICapabilityDefinition,
    AICapabilityPreview,
    AISkillExecutionView,
)
from .policy import AIToolPolicy, AIToolSpec
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

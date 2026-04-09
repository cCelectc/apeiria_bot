"""Tool registry, policy, and capability bridge for the AI domain."""

from .admin_models import AICapabilityDefinition, AICapabilityPreview
from .bridge import (
    AINoneBotCapabilityBridge,
    CapabilityNotAllowedError,
    ToolPolicyDeniedError,
    invoke_capability_with_policy,
)
from .intent_builders import build_capability_intents
from .models import (
    AICapabilityInvokeObservationOutput,
    AIMemoryQueryObservationInput,
    AIMemoryQueryObservationOutput,
    AINoneBotCapabilityRequest,
    AIPluginInspectCapabilityInput,
    AIPluginInspectCapabilityOutput,
    AIRelationshipInspectObservationOutput,
    AIToolCapabilityMode,
    AIToolExecutionView,
    AIToolIntent,
    AIToolIntentKind,
    AIToolObservationRequest,
    AIToolObservationResult,
    AIToolPolicy,
    AIToolPolicyDecision,
    AIToolRiskLevel,
    AIToolSpec,
    AIToolTurnCreateInput,
)
from .policy import evaluate_tool_policy
from .registry import AIToolRegistry
from .resolver import (
    AIToolSceneContext,
    AIToolScenePolicyProfile,
    resolve_default_tool_policy,
)
from .selection import plan_tool_intents_for_message, select_tools_for_message

__all__ = [
    "AICapabilityDefinition",
    "AICapabilityInvokeObservationOutput",
    "AICapabilityPreview",
    "AIMemoryQueryObservationInput",
    "AIMemoryQueryObservationOutput",
    "AINoneBotCapabilityBridge",
    "AINoneBotCapabilityRequest",
    "AIPluginInspectCapabilityInput",
    "AIPluginInspectCapabilityOutput",
    "AIRelationshipInspectObservationOutput",
    "AIToolCapabilityMode",
    "AIToolExecutionView",
    "AIToolIntent",
    "AIToolIntentKind",
    "AIToolObservationRequest",
    "AIToolObservationResult",
    "AIToolPolicy",
    "AIToolPolicyDecision",
    "AIToolRegistry",
    "AIToolRiskLevel",
    "AIToolSceneContext",
    "AIToolScenePolicyProfile",
    "AIToolSpec",
    "AIToolTurnCreateInput",
    "CapabilityNotAllowedError",
    "ToolPolicyDeniedError",
    "build_capability_intents",
    "evaluate_tool_policy",
    "invoke_capability_with_policy",
    "plan_tool_intents_for_message",
    "resolve_default_tool_policy",
    "select_tools_for_message",
]

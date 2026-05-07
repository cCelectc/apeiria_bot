"""Tool boundary exports with lazy runtime/service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .debug import AICapabilityPreview, AIToolIntentPreview
from .models import (
    AIMemoryQueryObservationInput,
    AIMemoryQueryObservationOutput,
    AIMemoryUpdateInput,
    AIMemoryUpdateObservationOutput,
    AIPluginInspectCapabilityInput,
    AIPluginInspectCapabilityOutput,
    AIRelationshipInspectObservationOutput,
    AIToolCapabilityMode,
    AIToolExecutionContext,
    AIToolExecutionRequest,
    AIToolExecutionStatus,
    AIToolExecutionView,
    AIToolIntent,
    AIToolIntentKind,
    AIToolObservationResult,
    AIToolOrigin,
    AIToolPolicy,
    AIToolPolicyDecision,
    AIToolResult,
    AIToolRiskLevel,
    AIToolTurnCreateInput,
)

if TYPE_CHECKING:
    from .contracts import AIToolExecutionCreateInput
    from .loop.projection import ToolResult
    from .policy import (
        AIToolPolicyBindingCreateInput,
        AIToolPolicyBindingService,
        AIToolPolicyBindingSpec,
        AIToolPolicyBindingTarget,
        AIToolSceneContext,
        AIToolScenePolicyProfile,
        ai_tool_policy_binding_service,
        evaluate_tool_policy,
        resolve_default_tool_policy,
        resolve_tool_policy_binding,
        summarize_tool_policy,
        tool_policy_binding_to_profile,
    )
    from .service import AIToolService, ai_tool_service

__all__ = [
    "AICapabilityPreview",
    "AIMemoryQueryObservationInput",
    "AIMemoryQueryObservationOutput",
    "AIMemoryUpdateInput",
    "AIMemoryUpdateObservationOutput",
    "AIPluginInspectCapabilityInput",
    "AIPluginInspectCapabilityOutput",
    "AIRelationshipInspectObservationOutput",
    "AIToolCapabilityMode",
    "AIToolExecutionContext",
    "AIToolExecutionCreateInput",
    "AIToolExecutionRequest",
    "AIToolExecutionStatus",
    "AIToolExecutionView",
    "AIToolIntent",
    "AIToolIntentKind",
    "AIToolIntentPreview",
    "AIToolObservationResult",
    "AIToolOrigin",
    "AIToolPolicy",
    "AIToolPolicyBindingCreateInput",
    "AIToolPolicyBindingService",
    "AIToolPolicyBindingSpec",
    "AIToolPolicyBindingTarget",
    "AIToolPolicyDecision",
    "AIToolResult",
    "AIToolRiskLevel",
    "AIToolSceneContext",
    "AIToolScenePolicyProfile",
    "AIToolService",
    "AIToolTurnCreateInput",
    "ToolResult",
    "ai_tool_policy_binding_service",
    "ai_tool_service",
    "evaluate_tool_policy",
    "resolve_default_tool_policy",
    "resolve_tool_policy_binding",
    "summarize_tool_policy",
    "tool_policy_binding_to_profile",
]

_LAZY_EXPORTS = {
    "AIToolExecutionCreateInput": ".contracts",
    "AIToolPolicyBindingCreateInput": ".policy",
    "AIToolPolicyBindingService": ".policy",
    "AIToolPolicyBindingSpec": ".policy",
    "AIToolPolicyBindingTarget": ".policy",
    "AIToolSceneContext": ".policy",
    "AIToolScenePolicyProfile": ".policy",
    "AIToolService": ".service",
    "ToolResult": ".loop.projection",
    "ai_tool_policy_binding_service": ".policy",
    "ai_tool_service": ".service",
    "evaluate_tool_policy": ".policy",
    "resolve_default_tool_policy": ".policy",
    "resolve_tool_policy_binding": ".policy",
    "summarize_tool_policy": ".policy",
    "tool_policy_binding_to_profile": ".policy",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    return getattr(module, name)

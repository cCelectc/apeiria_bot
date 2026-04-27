"""Tool boundary exports with lazy runtime/service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .debug import AICapabilityDefinition, AICapabilityPreview, AIToolIntentPreview
from .models import (
    AICapabilityInvokeObservationOutput,
    AIMemoryQueryObservationInput,
    AIMemoryQueryObservationOutput,
    AIMemoryUpdateInput,
    AIMemoryUpdateObservationOutput,
    AINoneBotCapabilityRequest,
    AIPluginInspectCapabilityInput,
    AIPluginInspectCapabilityOutput,
    AIRelationshipInspectObservationOutput,
    AIToolCapabilityMode,
    AIToolExecutionContext,
    AIToolExecutionStatus,
    AIToolExecutionView,
    AIToolIntent,
    AIToolIntentKind,
    AIToolObservationRequest,
    AIToolObservationResult,
    AIToolOrigin,
    AIToolPolicy,
    AIToolPolicyDecision,
    AIToolResult,
    AIToolRiskLevel,
    AIToolSpec,
    AIToolTurnCreateInput,
)

if TYPE_CHECKING:
    from .contracts import AIToolExecutionCreateInput
    from .gateway import (
        ToolGateway,
        ToolGatewayRequest,
        ToolGatewayResult,
        ToolResult,
        tool_gateway,
    )
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
    "AICapabilityDefinition",
    "AICapabilityInvokeObservationOutput",
    "AICapabilityPreview",
    "AIMemoryQueryObservationInput",
    "AIMemoryQueryObservationOutput",
    "AIMemoryUpdateInput",
    "AIMemoryUpdateObservationOutput",
    "AINoneBotCapabilityRequest",
    "AIPluginInspectCapabilityInput",
    "AIPluginInspectCapabilityOutput",
    "AIRelationshipInspectObservationOutput",
    "AIToolCapabilityMode",
    "AIToolExecutionContext",
    "AIToolExecutionCreateInput",
    "AIToolExecutionStatus",
    "AIToolExecutionView",
    "AIToolIntent",
    "AIToolIntentKind",
    "AIToolIntentPreview",
    "AIToolObservationRequest",
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
    "AIToolSpec",
    "AIToolTurnCreateInput",
    "ToolGateway",
    "ToolGatewayRequest",
    "ToolGatewayResult",
    "ToolResult",
    "ai_tool_policy_binding_service",
    "ai_tool_service",
    "evaluate_tool_policy",
    "resolve_default_tool_policy",
    "resolve_tool_policy_binding",
    "summarize_tool_policy",
    "tool_gateway",
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
    "ToolGateway": ".gateway",
    "ToolGatewayRequest": ".gateway",
    "ToolGatewayResult": ".gateway",
    "ToolResult": ".gateway",
    "ai_tool_policy_binding_service": ".policy",
    "ai_tool_service": ".service",
    "evaluate_tool_policy": ".policy",
    "resolve_default_tool_policy": ".policy",
    "resolve_tool_policy_binding": ".policy",
    "summarize_tool_policy": ".policy",
    "tool_gateway": ".gateway",
    "tool_policy_binding_to_profile": ".policy",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    return getattr(module, name)

"""Tool boundary exports with lazy runtime/service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .models import (
    AIRelationshipInspectObservationOutput,
    AIToolDefinition,
    AIToolExecutionContext,
    AIToolExecutionRequest,
    AIToolExecutionStatus,
    AIToolExecutionView,
    AIToolIntent,
    AIToolIntentKind,
    AIToolIntentPreview,
    AIToolLevel,
    AIToolObservationResult,
    AIToolOrigin,
    AIToolPolicy,
    AIToolPolicyDecision,
    AIToolReadiness,
    AIToolResult,
    AIToolTurnCreateInput,
    coerce_tool_level,
    tool_level_allows,
)

if TYPE_CHECKING:
    from .contracts import AIToolObservationCreateInput
    from .loop.projection import ToolResult
    from .policy import (
        AIToolPolicyBindingCreateInput,
        AIToolPolicyBindingService,
        AIToolPolicyBindingSpec,
        AIToolPolicyBindingTarget,
        AIToolSceneContext,
        ai_tool_policy_binding_service,
        evaluate_tool_policy,
        resolve_default_tool_policy,
        resolve_tool_policy_binding,
        summarize_tool_policy,
    )
    from .service import AIToolService, ai_tool_service

__all__ = [
    "AIRelationshipInspectObservationOutput",
    "AIToolDefinition",
    "AIToolExecutionContext",
    "AIToolExecutionRequest",
    "AIToolExecutionStatus",
    "AIToolExecutionView",
    "AIToolIntent",
    "AIToolIntentKind",
    "AIToolIntentPreview",
    "AIToolLevel",
    "AIToolObservationCreateInput",
    "AIToolObservationResult",
    "AIToolOrigin",
    "AIToolPolicy",
    "AIToolPolicyBindingCreateInput",
    "AIToolPolicyBindingService",
    "AIToolPolicyBindingSpec",
    "AIToolPolicyBindingTarget",
    "AIToolPolicyDecision",
    "AIToolReadiness",
    "AIToolResult",
    "AIToolSceneContext",
    "AIToolService",
    "AIToolTurnCreateInput",
    "ToolResult",
    "ai_tool_policy_binding_service",
    "ai_tool_service",
    "coerce_tool_level",
    "evaluate_tool_policy",
    "resolve_default_tool_policy",
    "resolve_tool_policy_binding",
    "summarize_tool_policy",
    "tool_level_allows",
]

_LAZY_EXPORTS = {
    "AIToolObservationCreateInput": ".contracts",
    "AIToolPolicyBindingCreateInput": ".policy",
    "AIToolPolicyBindingService": ".policy",
    "AIToolPolicyBindingSpec": ".policy",
    "AIToolPolicyBindingTarget": ".policy",
    "AIToolSceneContext": ".policy",
    "AIToolService": ".service",
    "ToolResult": ".loop.projection",
    "ai_tool_policy_binding_service": ".policy",
    "ai_tool_service": ".service",
    "evaluate_tool_policy": ".policy",
    "resolve_default_tool_policy": ".policy",
    "resolve_tool_policy_binding": ".policy",
    "summarize_tool_policy": ".policy",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    return getattr(module, name)

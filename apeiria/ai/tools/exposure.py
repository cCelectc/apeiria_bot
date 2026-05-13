"""Level-based AI tool exposure planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from apeiria.ai.tools.policy import evaluate_tool_policy

if TYPE_CHECKING:
    from apeiria.ai.tools.models import AIToolDefinition, AIToolLevel, AIToolPolicy

_UNSUPPORTED_MODEL_REASON = "model does not support tool calling"


@dataclass(frozen=True)
class AIToolExposureDiagnostic:
    """Diagnostic for one tool exposure decision."""

    tool_name: str
    required_level: "AIToolLevel"
    allowed_level: "AIToolLevel"
    readiness_code: str
    readiness_reason: str
    enabled: bool
    exposed: bool
    reason: str
    unsupported_model_reason: str | None = None


@dataclass(frozen=True)
class AIToolExposurePlan:
    """Provider-neutral set of model-visible tools plus reasons for omissions."""

    visible_tools: tuple["AIToolDefinition", ...] = ()
    unavailable_reasons: dict[str, str] = field(default_factory=dict)
    denied_reasons: dict[str, str] = field(default_factory=dict)
    diagnostics: dict[str, AIToolExposureDiagnostic] = field(default_factory=dict)

    @property
    def visible_tool_names(self) -> tuple[str, ...]:
        return tuple(tool.name for tool in self.visible_tools)


def create_tool_exposure_plan(
    *,
    tools: tuple["AIToolDefinition", ...],
    policy: "AIToolPolicy",
    model_supports_tools: bool,
) -> AIToolExposurePlan:
    """Expose tools whose model support, readiness, enabled state, and level pass."""

    visible_tools: list["AIToolDefinition"] = []
    unavailable_reasons: dict[str, str] = {}
    denied_reasons: dict[str, str] = {}
    diagnostics: dict[str, AIToolExposureDiagnostic] = {}

    for tool in tools:
        if not model_supports_tools:
            reason = _UNSUPPORTED_MODEL_REASON
            unavailable_reasons[tool.name] = reason
            diagnostics[tool.name] = _diagnostic(
                tool=tool,
                policy=policy,
                exposed=False,
                reason=reason,
                unsupported_model_reason=reason,
            )
            continue

        decision = evaluate_tool_policy(tool, policy)
        if decision.allowed:
            visible_tools.append(tool)
            diagnostics[tool.name] = _diagnostic(
                tool=tool,
                policy=policy,
                exposed=True,
                reason=decision.reason,
            )
            continue

        if not tool.enabled or not tool.readiness.ready:
            unavailable_reasons[tool.name] = decision.reason
        else:
            denied_reasons[tool.name] = decision.reason
        diagnostics[tool.name] = _diagnostic(
            tool=tool,
            policy=policy,
            exposed=False,
            reason=decision.reason,
        )

    return AIToolExposurePlan(
        visible_tools=tuple(visible_tools),
        unavailable_reasons=unavailable_reasons,
        denied_reasons=denied_reasons,
        diagnostics=diagnostics,
    )


def _diagnostic(
    *,
    tool: "AIToolDefinition",
    policy: "AIToolPolicy",
    exposed: bool,
    reason: str,
    unsupported_model_reason: str | None = None,
) -> AIToolExposureDiagnostic:
    return AIToolExposureDiagnostic(
        tool_name=tool.name,
        required_level=tool.required_level,
        allowed_level=policy.allowed_level,
        readiness_code=tool.readiness.code,
        readiness_reason=tool.readiness.reason,
        enabled=tool.enabled,
        exposed=exposed,
        reason=reason,
        unsupported_model_reason=unsupported_model_reason,
    )


__all__ = [
    "AIToolExposureDiagnostic",
    "AIToolExposurePlan",
    "create_tool_exposure_plan",
]

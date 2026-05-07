"""Capability exposure and execution policy decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .bindings import AICapabilityBindingType
from .contracts import AICapabilityContract, AICapabilityKind, AICapabilityRiskLevel

if TYPE_CHECKING:
    from .bindings import AICapabilityBinding


@dataclass(frozen=True)
class AICapabilityExposureProfile:
    """Simple policy facts for one capability exposure pass."""

    execution_enabled: bool = False
    allowed_names: frozenset[str] | None = None
    denied_names: frozenset[str] = frozenset()
    hidden_names: frozenset[str] = frozenset()
    active_prompt_skill_names: frozenset[str] = frozenset()
    allow_high_risk: bool = False
    allow_host_actions: bool = False
    max_risk_level: AICapabilityRiskLevel = "medium"


@dataclass(frozen=True)
class AICapabilityExposureContext:
    """Inputs for exposure-time capability policy."""

    profile: AICapabilityExposureProfile
    model_supports_tools: bool = True


@dataclass(frozen=True)
class AICapabilityExecutionContext:
    """Inputs for execution-time capability policy."""

    profile: AICapabilityExposureProfile


@dataclass(frozen=True)
class AICapabilityExposureDecision:
    """Exposure-time policy result."""

    visible: bool
    reason: str = "allowed"
    reason_kind: str | None = None


@dataclass(frozen=True)
class AICapabilityExecutionDecision:
    """Execution-time policy result."""

    allowed: bool
    reason: str
    prompt_safe_observation: str | None = None


def evaluate_capability_exposure(
    contract: AICapabilityContract,
    *,
    binding: "AICapabilityBinding | None",
    context: AICapabilityExposureContext,
) -> AICapabilityExposureDecision:
    """Decide whether a contract is visible for one model turn."""

    profile = context.profile
    baseline = _evaluate_baseline_contract_rules(contract, profile)
    if baseline is not None:
        return baseline
    if contract.kind is AICapabilityKind.EXECUTABLE:
        return _evaluate_executable_visibility(binding=binding, context=context)
    if contract.kind is AICapabilityKind.PROMPT_SKILL:
        return _evaluate_prompt_skill_visibility(
            contract=contract,
            binding=binding,
            profile=profile,
        )
    return AICapabilityExposureDecision(visible=True)


def evaluate_capability_execution(
    *,
    contract: AICapabilityContract,
    binding: "AICapabilityBinding | None",
    context: AICapabilityExecutionContext,
) -> AICapabilityExecutionDecision:
    """Re-check a selected executable capability before invocation."""

    if binding is None:
        return _execution_denied(contract.name, "no executable binding")
    decision = evaluate_capability_exposure(
        contract,
        binding=binding,
        context=AICapabilityExposureContext(
            profile=context.profile,
            model_supports_tools=True,
        ),
    )
    if not decision.visible:
        return _execution_denied(contract.name, decision.reason)
    return AICapabilityExecutionDecision(allowed=True, reason="allowed")


def _evaluate_baseline_contract_rules(
    contract: AICapabilityContract,
    profile: AICapabilityExposureProfile,
) -> AICapabilityExposureDecision | None:
    if contract.name in profile.hidden_names:
        return AICapabilityExposureDecision(
            visible=False,
            reason="hidden by visibility rules",
            reason_kind="hidden",
        )
    if contract.name in profile.denied_names:
        return AICapabilityExposureDecision(
            visible=False,
            reason="explicitly denied",
            reason_kind="denied",
        )
    if profile.allowed_names is not None and contract.name not in profile.allowed_names:
        return AICapabilityExposureDecision(
            visible=False,
            reason="not in allowlist",
            reason_kind="denied",
        )
    if not _risk_allowed(contract.safety.risk_level, profile):
        return AICapabilityExposureDecision(
            visible=False,
            reason=f"risk level {contract.safety.risk_level!r} is not enabled",
            reason_kind="denied",
        )
    return None


def _evaluate_executable_visibility(
    *,
    binding: "AICapabilityBinding | None",
    context: AICapabilityExposureContext,
) -> AICapabilityExposureDecision:
    if not context.profile.execution_enabled:
        return AICapabilityExposureDecision(
            visible=False,
            reason="execution is disabled",
            reason_kind="unavailable",
        )
    if not context.model_supports_tools:
        return AICapabilityExposureDecision(
            visible=False,
            reason="selected model does not support tools",
            reason_kind="unavailable",
        )
    if binding is None:
        return AICapabilityExposureDecision(
            visible=False,
            reason="missing binding",
            reason_kind="unavailable",
        )
    if (
        binding.binding_type is AICapabilityBindingType.HOST_ACTION
        and not context.profile.allow_host_actions
    ):
        return AICapabilityExposureDecision(
            visible=False,
            reason="host actions are not enabled",
            reason_kind="denied",
        )
    return AICapabilityExposureDecision(visible=True)


def _evaluate_prompt_skill_visibility(
    *,
    contract: AICapabilityContract,
    binding: "AICapabilityBinding | None",
    profile: AICapabilityExposureProfile,
) -> AICapabilityExposureDecision:
    if contract.name not in profile.active_prompt_skill_names:
        return AICapabilityExposureDecision(
            visible=False,
            reason="prompt skill is not active",
            reason_kind="hidden",
        )
    if binding is None:
        return AICapabilityExposureDecision(
            visible=False,
            reason="missing prompt binding",
            reason_kind="unavailable",
        )
    return AICapabilityExposureDecision(visible=True)


def _execution_denied(
    contract_name: str,
    reason: str,
) -> AICapabilityExecutionDecision:
    return AICapabilityExecutionDecision(
        allowed=False,
        reason=reason,
        prompt_safe_observation=(
            f"Capability {contract_name!r} was not executed: {reason}."
        ),
    )


def _risk_allowed(
    risk_level: AICapabilityRiskLevel,
    profile: AICapabilityExposureProfile,
) -> bool:
    if profile.allow_high_risk:
        return True
    order = {"low": 0, "medium": 1, "high": 2}
    return order[risk_level] <= order[profile.max_risk_level]

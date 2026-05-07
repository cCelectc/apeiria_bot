"""Provider-neutral capability projections."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from apeiria.ai.model.runtime.adapter import AIModelToolDefinition

from .contracts import AICapabilityContract, AICapabilityKind
from .diagnostics import AICapabilityExposureDiagnostics
from .policy import AICapabilityExposureContext, evaluate_capability_exposure

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .bindings import AICapabilityBindingSnapshot
    from .registry import AICapabilityContractSnapshot


@dataclass(frozen=True)
class AIPromptSkillActivation:
    """Prompt-skill content selected for one turn."""

    name: str
    body_markdown: str
    required_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class AICapabilityExposurePlan:
    """Immutable per-turn capability exposure view."""

    model_visible_tools: tuple[AIModelToolDefinition, ...] = ()
    prompt_activations: tuple[AIPromptSkillActivation, ...] = ()
    binding_map: Mapping[str, str] | None = None
    hidden_reasons: Mapping[str, str] | None = None
    denied_reasons: Mapping[str, str] | None = None
    unavailable_reasons: Mapping[str, str] | None = None
    diagnostics: AICapabilityExposureDiagnostics | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "binding_map",
            "hidden_reasons",
            "denied_reasons",
            "unavailable_reasons",
        ):
            value = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                MappingProxyType(dict(value or {})),
            )


def project_executable_contract(
    contract: AICapabilityContract,
) -> AIModelToolDefinition:
    """Project one executable contract to a provider-neutral tool definition."""

    return AIModelToolDefinition(
        name=_contract_name_to_function_name(contract.name),
        description=contract.description,
        parameters=contract.input_schema,
    )


def project_prompt_skill_activation(
    contract: AICapabilityContract,
    *,
    body_markdown: str,
    required_capabilities: tuple[str, ...] = (),
) -> AIPromptSkillActivation:
    """Project one prompt skill to an activation payload."""

    return AIPromptSkillActivation(
        name=contract.name,
        body_markdown=body_markdown,
        required_capabilities=required_capabilities,
    )


def create_capability_exposure_plan(
    *,
    contracts: "AICapabilityContractSnapshot",
    bindings: "AICapabilityBindingSnapshot",
    context: AICapabilityExposureContext,
) -> AICapabilityExposurePlan:
    """Compile per-turn contract and binding visibility."""

    model_tools: list[AIModelToolDefinition] = []
    prompt_activations: list[AIPromptSkillActivation] = []
    binding_map: dict[str, str] = {}
    hidden_reasons: dict[str, str] = {}
    denied_reasons: dict[str, str] = {}
    unavailable_reasons: dict[str, str] = {}

    for contract in contracts.contracts:
        binding = bindings.by_contract.get(contract.name)
        decision = evaluate_capability_exposure(
            contract,
            binding=binding,
            context=context,
        )
        if not decision.visible:
            _record_reason(
                contract.name,
                reason=decision.reason,
                reason_kind=decision.reason_kind,
                reasons=(hidden_reasons, denied_reasons, unavailable_reasons),
            )
            continue
        if contract.kind is AICapabilityKind.EXECUTABLE:
            _append_executable_projection(
                contract=contract,
                binding_key=binding.binding_key if binding is not None else None,
                model_tools=model_tools,
                binding_map=binding_map,
            )
        elif (
            contract.kind is AICapabilityKind.PROMPT_SKILL
            and binding is not None
            and binding.load_prompt is not None
        ):
            prompt_activations.append(
                project_prompt_skill_activation(
                    contract,
                    body_markdown=binding.load_prompt(),
                    required_capabilities=binding.required_capabilities,
                )
            )

    return AICapabilityExposurePlan(
        model_visible_tools=tuple(model_tools),
        prompt_activations=tuple(prompt_activations),
        binding_map=binding_map,
        hidden_reasons=hidden_reasons,
        denied_reasons=denied_reasons,
        unavailable_reasons=unavailable_reasons,
        diagnostics=AICapabilityExposureDiagnostics(
            total_contracts=len(contracts.contracts),
            visible_tools=len(model_tools),
            prompt_activations=len(prompt_activations),
            hidden_count=len(hidden_reasons),
            denied_count=len(denied_reasons),
            unavailable_count=len(unavailable_reasons),
            model_supports_tools=context.model_supports_tools,
        ),
    )


def _append_executable_projection(
    *,
    contract: AICapabilityContract,
    binding_key: str | None,
    model_tools: list[AIModelToolDefinition],
    binding_map: dict[str, str],
) -> None:
    model_tools.append(project_executable_contract(contract))
    if binding_key is not None:
        binding_map[contract.name] = binding_key


def _record_reason(
    contract_name: str,
    *,
    reason: str,
    reason_kind: str | None,
    reasons: tuple[dict[str, str], dict[str, str], dict[str, str]],
) -> None:
    hidden_reasons, denied_reasons, unavailable_reasons = reasons
    if reason_kind == "hidden":
        hidden_reasons[contract_name] = reason
    elif reason_kind == "denied":
        denied_reasons[contract_name] = reason
    else:
        unavailable_reasons[contract_name] = reason


def _contract_name_to_function_name(contract_name: str) -> str:
    return contract_name.replace(".", "_")

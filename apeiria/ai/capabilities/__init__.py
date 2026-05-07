"""Provider-neutral AI capability contracts and bindings."""

from __future__ import annotations

from .adapters import (
    capability_contract_from_skill_definition,
    capability_contract_from_skill_file,
)
from .bindings import (
    AICapabilityBinding,
    AICapabilityBindingSnapshot,
    AICapabilityBindingType,
    AILocalToolHandler,
    AIPromptSkillLoader,
    create_host_action_binding,
    create_local_tool_binding,
    create_prompt_skill_binding,
)
from .contracts import (
    AICapabilityContract,
    AICapabilityKind,
    AICapabilityOrigin,
    AICapabilityRiskLevel,
    AICapabilitySafety,
)
from .diagnostics import AICapabilityExposureDiagnostics
from .policy import (
    AICapabilityExecutionContext,
    AICapabilityExecutionDecision,
    AICapabilityExposureContext,
    AICapabilityExposureDecision,
    AICapabilityExposureProfile,
    evaluate_capability_execution,
    evaluate_capability_exposure,
)
from .projections import (
    AICapabilityExposurePlan,
    AIPromptSkillActivation,
    create_capability_exposure_plan,
    project_executable_contract,
    project_prompt_skill_activation,
)
from .registry import (
    AICapabilityBindingRegistry,
    AICapabilityContractRegistry,
    AICapabilityContractSnapshot,
    AIDuplicateCapabilityBindingError,
    AIDuplicateCapabilityContractError,
)

__all__ = [
    "AICapabilityBinding",
    "AICapabilityBindingRegistry",
    "AICapabilityBindingSnapshot",
    "AICapabilityBindingType",
    "AICapabilityContract",
    "AICapabilityContractRegistry",
    "AICapabilityContractSnapshot",
    "AICapabilityExecutionContext",
    "AICapabilityExecutionDecision",
    "AICapabilityExposureContext",
    "AICapabilityExposureDecision",
    "AICapabilityExposureDiagnostics",
    "AICapabilityExposurePlan",
    "AICapabilityExposureProfile",
    "AICapabilityKind",
    "AICapabilityOrigin",
    "AICapabilityRiskLevel",
    "AICapabilitySafety",
    "AIDuplicateCapabilityBindingError",
    "AIDuplicateCapabilityContractError",
    "AILocalToolHandler",
    "AIPromptSkillActivation",
    "AIPromptSkillLoader",
    "capability_contract_from_skill_definition",
    "capability_contract_from_skill_file",
    "create_capability_exposure_plan",
    "create_host_action_binding",
    "create_local_tool_binding",
    "create_prompt_skill_binding",
    "evaluate_capability_execution",
    "evaluate_capability_exposure",
    "project_executable_contract",
    "project_prompt_skill_activation",
]

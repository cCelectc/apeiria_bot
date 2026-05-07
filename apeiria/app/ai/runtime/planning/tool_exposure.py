"""Tool-exposure planning boundary."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime  # noqa: TC003
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from apeiria.ai.capabilities import (
    AICapabilityBindingSnapshot,
    AICapabilityContract,
    AICapabilityContractSnapshot,
    AICapabilityExposureContext,
    AICapabilityExposurePlan,
    AICapabilityExposureProfile,
    create_capability_exposure_plan,
)
from apeiria.ai.model.runtime.adapter import AIModelToolDefinition
from apeiria.ai.tools.function_calling import (
    build_function_tools,
    function_name_to_tool_name,
)
from apeiria.ai.turn_records import PromptSafeObservation

if TYPE_CHECKING:
    from apeiria.ai.tools import AIToolPolicy
    from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopInput


DEFAULT_TOOL_AWARENESS_CATEGORIES = (
    "memory",
    "future_task",
    "relationship",
    "plugin_capability",
)
_DISPLAY_TIMEZONE = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True, slots=True)
class ToolExposurePlan:
    """Provider-neutral plan for awareness and executable tool exposure."""

    awareness_text: str = ""
    category_ids: tuple[str, ...] = ()
    selected_tool_contracts: tuple[AICapabilityContract, ...] = ()
    selected_tools: tuple["AIModelToolDefinition", ...] = ()
    hidden_reasons: dict[str, str] = field(default_factory=dict)
    unavailable_reasons: dict[str, str] = field(default_factory=dict)
    denied_reasons: dict[str, str] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    capability_contracts: AICapabilityContractSnapshot | None = None
    capability_bindings: AICapabilityBindingSnapshot | None = None
    capability_plan: AICapabilityExposurePlan = field(
        default_factory=AICapabilityExposurePlan
    )

    @property
    def selected_tool_names(self) -> tuple[str, ...]:
        """Return selected executable tool names in model-visible order."""

        if self.capability_contracts is not None:
            return tuple(self.capability_plan.binding_map or {})
        if self.selected_tool_contracts:
            return tuple(tool.name for tool in self.selected_tool_contracts)
        return tuple(
            function_name_to_tool_name(tool.name) for tool in self.selected_tools
        )

    @property
    def has_executable_tools(self) -> bool:
        """Return whether this plan exposes executable tool definitions."""

        if self.capability_contracts is not None:
            return bool(self.capability_plan.model_visible_tools)
        return bool(self.selected_tool_contracts or self.selected_tools)


def compile_tool_exposure_provider_schema(
    plan: ToolExposurePlan,
    *,
    current_time: datetime | None = None,
) -> tuple["AIModelToolDefinition", ...]:
    """Compile selected logical tool specs into provider tool definitions."""

    if plan.capability_contracts is not None:
        return tuple(
            _with_runtime_projection_context(
                definition,
                current_time=current_time,
            )
            for definition in plan.capability_plan.model_visible_tools
        )
    if plan.selected_tool_contracts:
        return build_function_tools(
            list(plan.selected_tool_contracts),
            current_time=current_time,
        )
    return plan.selected_tools


def build_default_tool_exposure_plan(
    *,
    allowed_tools: tuple[AICapabilityContract, ...],
    ordinary_ambient_group: bool,
) -> ToolExposurePlan:
    """Build deterministic first-slice capability awareness for one turn."""

    hidden_reasons: dict[str, str] = {}
    admin_project_tool_count = 0
    for tool in allowed_tools:
        if _is_admin_project_tool(tool):
            admin_project_tool_count += 1
            if ordinary_ambient_group:
                hidden_reasons[tool.name] = "excluded_from_ambient_group"

    return ToolExposurePlan(
        awareness_text=_default_awareness_text(),
        category_ids=DEFAULT_TOOL_AWARENESS_CATEGORIES,
        selected_tools=(),
        hidden_reasons=hidden_reasons,
        diagnostics={
            "category_count": len(DEFAULT_TOOL_AWARENESS_CATEGORIES),
            "allowed_tool_count": len(allowed_tools),
            "admin_project_tool_count": admin_project_tool_count,
            "ordinary_ambient_group": ordinary_ambient_group,
        },
    )


def _default_awareness_text() -> str:
    return (
        "External capability categories may exist: memory, future_task, "
        "relationship, plugin_capability. Executable tools are selected "
        "separately; do not claim an external action unless a tool result is "
        "provided."
    )


def _is_admin_project_tool(tool: AICapabilityContract) -> bool:
    tags = set(tool.tags)
    return (
        "admin" in tags
        or "project_management" in tags
        or tool.name.startswith("admin.")
        or tool.name.startswith("project.")
    )


@dataclass(frozen=True, slots=True)
class ToolOrchestrator:
    """First-slice tool orchestration boundary."""

    def plan_exposure(  # noqa: PLR0913
        self,
        *,
        allowed_tools: tuple[AICapabilityContract, ...],
        contracts: AICapabilityContractSnapshot | None = None,
        bindings: AICapabilityBindingSnapshot | None = None,
        policy: "AIToolPolicy",
        requested_tool_names: tuple[str, ...] = (),
        ordinary_ambient_group: bool,
        execution_timeout_seconds: float | None,
        current_time: datetime | None = None,
        model_supports_tools: bool = True,
    ) -> ToolExposurePlan:
        """Plan awareness and selected executable tool definitions."""

        del current_time
        base_plan = build_default_tool_exposure_plan(
            allowed_tools=allowed_tools,
            ordinary_ambient_group=ordinary_ambient_group,
        )
        requested = set(requested_tool_names)
        selected_contracts: list[AICapabilityContract] = []
        unavailable_reasons: dict[str, str] = {}
        denied_reasons: dict[str, str] = {}

        for tool in allowed_tools:
            if requested and tool.name not in requested:
                continue
            reason = _policy_denial_reason(tool, policy)
            if reason is not None:
                denied_reasons[tool.name] = reason
                continue
            if not policy.execution_enabled:
                unavailable_reasons[tool.name] = "execution_disabled"
                continue
            if tool.name in base_plan.hidden_reasons:
                continue
            selected_contracts.append(tool)

        contract_snapshot = contracts or _contract_snapshot(tuple(selected_contracts))
        binding_snapshot = bindings or AICapabilityBindingSnapshot(
            bindings=(),
            by_key={},
            by_contract={},
        )
        capability_plan = _build_capability_exposure_plan(
            contracts=contract_snapshot,
            bindings=binding_snapshot,
            policy=policy,
            model_supports_tools=model_supports_tools,
        )
        capability_diagnostics = capability_plan.diagnostics

        return ToolExposurePlan(
            awareness_text=base_plan.awareness_text,
            category_ids=base_plan.category_ids,
            selected_tool_contracts=tuple(selected_contracts),
            hidden_reasons={
                **base_plan.hidden_reasons,
                **dict(capability_plan.hidden_reasons or {}),
            },
            unavailable_reasons={
                **unavailable_reasons,
                **dict(capability_plan.unavailable_reasons or {}),
            },
            denied_reasons={
                **denied_reasons,
                **dict(capability_plan.denied_reasons or {}),
            },
            diagnostics={
                **base_plan.diagnostics,
                "execution_timeout_seconds": execution_timeout_seconds,
                "parallel_safe_tool_names": tuple(
                    tool.name
                    for tool in selected_contracts
                    if tool.safety.concurrency_safe
                ),
                "selected_tool_count": len(capability_plan.model_visible_tools),
                "capability_contract_count": (
                    capability_diagnostics.total_contracts
                    if capability_diagnostics is not None
                    else 0
                ),
                "capability_visible_tool_count": (
                    capability_diagnostics.visible_tools
                    if capability_diagnostics is not None
                    else 0
                ),
                "capability_hidden_count": (
                    capability_diagnostics.hidden_count
                    if capability_diagnostics is not None
                    else 0
                ),
                "capability_denied_count": (
                    capability_diagnostics.denied_count
                    if capability_diagnostics is not None
                    else 0
                ),
                "capability_unavailable_count": (
                    capability_diagnostics.unavailable_count
                    if capability_diagnostics is not None
                    else 0
                ),
                "model_supports_tools": (
                    capability_diagnostics.model_supports_tools
                    if capability_diagnostics is not None
                    else True
                ),
            },
            capability_contracts=contract_snapshot,
            capability_bindings=binding_snapshot,
            capability_plan=capability_plan,
        )

    def build_denial_observation(
        self,
        *,
        tool_name: str,
        reason: str,
    ) -> PromptSafeObservation:
        """Build a bounded model-visible observation for denied tool calls."""

        content = f"Tool '{tool_name}' was not executed: {reason}."
        return PromptSafeObservation(
            content=content,
            truncated=False,
            original_length=len(content),
        )


def _policy_denial_reason(
    tool: AICapabilityContract,
    policy: "AIToolPolicy",
) -> str | None:
    if tool.name in policy.denied_tool_names:
        return "policy_denied"
    if (
        policy.allowed_tool_names is not None
        and tool.name not in policy.allowed_tool_names
    ):
        return "not_in_allowed_tool_names"
    if tool.safety.risk_level == "high" and not policy.allow_high_risk_tools:
        return "high_risk_denied"
    if tool.name.startswith(("plugin.", "help.")) and not policy.allow_host_actions:
        return "host_action_denied"
    return None


def _build_capability_exposure_plan(
    *,
    contracts: AICapabilityContractSnapshot,
    bindings: AICapabilityBindingSnapshot,
    policy: "AIToolPolicy",
    model_supports_tools: bool,
) -> AICapabilityExposurePlan:
    return create_capability_exposure_plan(
        contracts=contracts,
        bindings=bindings,
        context=AICapabilityExposureContext(
            profile=AICapabilityExposureProfile(
                execution_enabled=policy.execution_enabled,
                allowed_names=(
                    frozenset(policy.allowed_tool_names)
                    if policy.allowed_tool_names is not None
                    else None
                ),
                denied_names=frozenset(policy.denied_tool_names),
                allow_host_actions=policy.allow_host_actions,
                allow_high_risk=policy.allow_high_risk_tools,
                max_risk_level="high" if policy.allow_high_risk_tools else "medium",
            ),
            model_supports_tools=model_supports_tools,
        ),
    )


def _with_runtime_projection_context(
    definition: "AIModelToolDefinition",
    *,
    current_time: datetime | None,
) -> "AIModelToolDefinition":
    tool_name = function_name_to_tool_name(definition.name)
    if tool_name != "future_task.manage" or current_time is None:
        return definition
    localized = current_time.astimezone(_DISPLAY_TIMEZONE)
    return AIModelToolDefinition(
        name=definition.name,
        description=(
            f"{definition.description}. Current reference time: "
            f"{localized.isoformat()}. Convert relative times like tomorrow "
            "morning into absolute ISO-8601 timestamps with timezone offset "
            "before calling this tool."
        ),
        parameters=definition.parameters,
    )


def apply_tool_exposure_allowlist(
    request: "RuntimeToolLoopInput",
    plan: ToolExposurePlan,
) -> "RuntimeToolLoopInput":
    """Return a gateway request constrained by the runtime exposure plan."""

    if not hasattr(request, "executable_tool_names"):
        return request
    return replace(
        request,
        executable_tool_names=frozenset(_executable_tool_names(plan)),
        capability_binding_map=plan.capability_plan.binding_map,
        capability_contracts=(
            plan.capability_contracts.by_name
            if plan.capability_contracts is not None
            else None
        ),
        capability_bindings=(
            plan.capability_bindings.by_key
            if plan.capability_bindings is not None
            else None
        ),
    )


def _executable_tool_names(plan: ToolExposurePlan) -> tuple[str, ...]:
    if plan.capability_plan.binding_map:
        return tuple(plan.capability_plan.binding_map)
    if plan.selected_tool_contracts:
        return tuple(tool.name for tool in plan.selected_tool_contracts)
    return tuple(
        function_name_to_tool_name(tool.name)
        for tool in compile_tool_exposure_provider_schema(plan)
    )


__all__ = [
    "DEFAULT_TOOL_AWARENESS_CATEGORIES",
    "ToolExposurePlan",
    "ToolOrchestrator",
    "apply_tool_exposure_allowlist",
    "build_default_tool_exposure_plan",
    "compile_tool_exposure_provider_schema",
]


def _contract_snapshot(
    contracts: tuple[AICapabilityContract, ...],
) -> AICapabilityContractSnapshot:
    return AICapabilityContractSnapshot(
        contracts=tuple(sorted(contracts, key=lambda item: item.name)),
        by_name=MappingProxyType({contract.name: contract for contract in contracts}),
    )

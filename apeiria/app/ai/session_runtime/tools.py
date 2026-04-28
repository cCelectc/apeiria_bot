"""Tool exposure contracts for AI session runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Any

from apeiria.ai.tools.function_calling import build_function_tools
from apeiria.ai.turn_records import PromptSafeObservation

if TYPE_CHECKING:
    from apeiria.ai.model import AIModelToolDefinition
    from apeiria.ai.tools import AIToolPolicy, AIToolSpec


DEFAULT_TOOL_AWARENESS_CATEGORIES = (
    "memory",
    "future_task",
    "relationship",
    "plugin_capability",
)


@dataclass(frozen=True, slots=True)
class ToolExposurePlan:
    """Provider-neutral plan for awareness and executable tool exposure."""

    awareness_text: str = ""
    category_ids: tuple[str, ...] = ()
    selected_tools: tuple["AIModelToolDefinition", ...] = ()
    hidden_reasons: dict[str, str] = field(default_factory=dict)
    unavailable_reasons: dict[str, str] = field(default_factory=dict)
    denied_reasons: dict[str, str] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def selected_tool_names(self) -> tuple[str, ...]:
        """Return selected executable tool names in model-visible order."""

        return tuple(tool.name for tool in self.selected_tools)

    @property
    def has_executable_tools(self) -> bool:
        """Return whether this plan exposes executable tool definitions."""

        return bool(self.selected_tools)


def build_default_tool_exposure_plan(
    *,
    allowed_tools: tuple["AIToolSpec", ...],
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


def _is_admin_project_tool(tool: "AIToolSpec") -> bool:
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
        allowed_tools: tuple["AIToolSpec", ...],
        policy: "AIToolPolicy",
        requested_tool_names: tuple[str, ...] = (),
        ordinary_ambient_group: bool,
        execution_timeout_seconds: float | None,
        current_time: datetime | None = None,
    ) -> ToolExposurePlan:
        """Plan awareness and selected executable tool definitions."""

        base_plan = build_default_tool_exposure_plan(
            allowed_tools=allowed_tools,
            ordinary_ambient_group=ordinary_ambient_group,
        )
        requested = set(requested_tool_names)
        selected_specs: list[AIToolSpec] = []
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
            selected_specs.append(tool)

        selected_tools = build_function_tools(
            selected_specs,
            current_time=current_time,
        )
        return ToolExposurePlan(
            awareness_text=base_plan.awareness_text,
            category_ids=base_plan.category_ids,
            selected_tools=selected_tools,
            hidden_reasons=base_plan.hidden_reasons,
            unavailable_reasons=unavailable_reasons,
            denied_reasons=denied_reasons,
            diagnostics={
                **base_plan.diagnostics,
                "execution_timeout_seconds": execution_timeout_seconds,
                "parallel_safe_tool_names": tuple(
                    tool.name for tool in selected_specs if tool.concurrency_safe
                ),
                "selected_tool_count": len(selected_specs),
            },
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
    tool: "AIToolSpec",
    policy: "AIToolPolicy",
) -> str | None:
    if tool.name in policy.denied_tool_names:
        return "policy_denied"
    if (
        policy.allowed_tool_names is not None
        and tool.name not in policy.allowed_tool_names
    ):
        return "not_in_allowed_tool_names"
    if tool.risk_level == "high" and not policy.allow_high_risk_tools:
        return "high_risk_denied"
    if tool.is_capability_bridge and not policy.allow_capability_bridge:
        return "capability_bridge_denied"
    return None


@dataclass(frozen=True, slots=True)
class ToolGatewayMigrationAdapter:
    """Adapter that invokes the existing ToolGateway with selected tools only."""

    gateway: Any

    async def run_tool_loop(
        self,
        *,
        request: object,
        messages: tuple[object, ...],
        exposure_plan: ToolExposurePlan,
        selected_model: object,
        fallback_models: tuple[object, ...],
    ) -> object:
        """Run the existing gateway using the orchestrator-selected definitions."""

        return await self.gateway.run_tool_loop(
            request,
            messages=list(messages),
            tools=exposure_plan.selected_tools,
            selected=selected_model,
            fallback_models=fallback_models,
        )

"""Tool-exposure planning boundary."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from apeiria.ai.model.runtime.adapter import AIModelToolDefinition
from apeiria.ai.tools.exposure import AIToolExposurePlan, create_tool_exposure_plan
from apeiria.ai.tools.function_calling import build_function_tools
from apeiria.ai.tools.projection import build_provider_name_map
from apeiria.ai.turn_records import PromptSafeObservation

if TYPE_CHECKING:
    from apeiria.ai.tools import AIToolPolicy
    from apeiria.ai.tools.models import AIToolDefinition
    from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopInput


DEFAULT_TOOL_AWARENESS_CATEGORIES = (
    "memory",
    "future_task",
    "relationship",
    "plugin_capability",
)
_DISPLAY_TIMEZONE = ZoneInfo("Asia/Shanghai")
_MAX_TOOL_GUIDANCE_DESCRIPTION_CHARS = 160


@dataclass(frozen=True, slots=True)
class ToolExposurePlan:
    """Provider-neutral plan for awareness and executable tool exposure."""

    awareness_text: str = ""
    category_ids: tuple[str, ...] = ()
    selected_tool_definitions: tuple[AIToolDefinition, ...] = ()
    selected_tools: tuple["AIModelToolDefinition", ...] = ()
    hidden_reasons: dict[str, str] = field(default_factory=dict)
    unavailable_reasons: dict[str, str] = field(default_factory=dict)
    denied_reasons: dict[str, str] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    provider_name_map: dict[str, str] = field(default_factory=dict)
    exposure_plan: AIToolExposurePlan = field(default_factory=AIToolExposurePlan)

    @property
    def selected_tool_names(self) -> tuple[str, ...]:
        """Return selected executable stable tool names in model-visible order."""

        if self.selected_tool_definitions:
            return tuple(tool.name for tool in self.selected_tool_definitions)
        return tuple(
            self.provider_name_map.get(tool.name, tool.name)
            for tool in self.selected_tools
        )

    @property
    def has_executable_tools(self) -> bool:
        """Return whether this plan exposes executable tool definitions."""

        return bool(self.selected_tool_definitions or self.selected_tools)


def compile_tool_exposure_provider_schema(
    plan: ToolExposurePlan,
    *,
    current_time: datetime | None = None,
) -> tuple["AIModelToolDefinition", ...]:
    """Compile selected logical tool specs into adapter-neutral tool definitions."""

    if plan.selected_tool_definitions:
        return tuple(
            _with_runtime_projection_context(
                definition,
                current_time=current_time,
            )
            for definition in build_function_tools(
                list(plan.selected_tool_definitions),
                current_time=current_time,
            )
        )
    return plan.selected_tools


def build_tool_guidance_text(plan: ToolExposurePlan) -> str | None:
    """Build compact prompt guidance from the actual exposed tool set."""

    if plan.selected_tool_definitions:
        lines = [
            _tool_guidance_line(
                tool,
                provider_name=_provider_name_for_tool(plan, tool.name),
            )
            for tool in plan.selected_tool_definitions
        ]
    else:
        lines = [
            (f"- {tool.name}: {_bounded_tool_guidance_description(tool.description)}")
            for tool in plan.selected_tools
        ]
    if not lines:
        return None
    return "\n".join(
        (
            "Model-visible tools this turn:",
            *lines,
            (
                "Call a tool only when its description matches a needed lookup "
                "or action; answer directly when current context is enough."
            ),
            "Do not claim a tool result unless a tool observation is provided.",
        )
    )


def build_default_tool_exposure_plan(
    *,
    allowed_tools: tuple[AIToolDefinition, ...],
    ordinary_ambient_group: bool,
) -> ToolExposurePlan:
    """Build deterministic first-slice tool awareness for one turn."""

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


def _is_admin_project_tool(tool: AIToolDefinition) -> bool:
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
        allowed_tools: tuple[AIToolDefinition, ...],
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
        candidate_tools = tuple(
            tool
            for tool in allowed_tools
            if (not requested or tool.name in requested)
            and tool.name not in base_plan.hidden_reasons
        )
        exposure_plan = create_tool_exposure_plan(
            tools=candidate_tools,
            policy=policy,
            model_supports_tools=model_supports_tools,
        )
        provider_name_map = build_provider_name_map(exposure_plan.visible_tools)

        return ToolExposurePlan(
            awareness_text=base_plan.awareness_text,
            category_ids=base_plan.category_ids,
            selected_tool_definitions=exposure_plan.visible_tools,
            hidden_reasons=base_plan.hidden_reasons,
            unavailable_reasons=exposure_plan.unavailable_reasons,
            denied_reasons=exposure_plan.denied_reasons,
            diagnostics={
                **base_plan.diagnostics,
                "execution_timeout_seconds": execution_timeout_seconds,
                "parallel_safe_tool_names": (),
                "selected_tool_count": len(exposure_plan.visible_tools),
                "model_supports_tools": model_supports_tools,
                "tool_exposure": exposure_plan.diagnostics,
            },
            provider_name_map=provider_name_map,
            exposure_plan=exposure_plan,
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


def _with_runtime_projection_context(
    definition: "AIModelToolDefinition",
    *,
    current_time: datetime | None,
) -> "AIModelToolDefinition":
    if not definition.name.startswith("future_task_") or current_time is None:
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


def _tool_guidance_line(
    tool: "AIToolDefinition",
    *,
    provider_name: str,
) -> str:
    return (
        f"- {provider_name} ({tool.name}, {tool.required_level.value}): "
        f"{_bounded_tool_guidance_description(tool.description)}"
    )


def _provider_name_for_tool(plan: ToolExposurePlan, tool_name: str) -> str:
    for provider_name, stable_name in plan.provider_name_map.items():
        if stable_name == tool_name:
            return provider_name
    return tool_name


def _bounded_tool_guidance_description(description: str) -> str:
    normalized = " ".join(description.split())
    if len(normalized) <= _MAX_TOOL_GUIDANCE_DESCRIPTION_CHARS:
        return normalized
    return f"{normalized[: _MAX_TOOL_GUIDANCE_DESCRIPTION_CHARS - 1].rstrip()}..."


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
        provider_name_map=plan.provider_name_map,
    )


def _executable_tool_names(plan: ToolExposurePlan) -> tuple[str, ...]:
    if plan.selected_tool_definitions:
        return tuple(tool.name for tool in plan.selected_tool_definitions)
    return tuple(
        plan.provider_name_map.get(tool.name, tool.name) for tool in plan.selected_tools
    )


__all__ = [
    "DEFAULT_TOOL_AWARENESS_CATEGORIES",
    "ToolExposurePlan",
    "ToolOrchestrator",
    "apply_tool_exposure_allowlist",
    "build_default_tool_exposure_plan",
    "build_tool_guidance_text",
    "compile_tool_exposure_provider_schema",
]

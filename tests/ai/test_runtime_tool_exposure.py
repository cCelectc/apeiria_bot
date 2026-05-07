# ruff: noqa: PLR2004

from __future__ import annotations

from datetime import datetime, timezone

from apeiria.ai.model import AIModelToolDefinition
from apeiria.ai.tools import AIToolPolicy, AIToolSpec, ToolGatewayRequest
from apeiria.app.ai.runtime.planning.tool_exposure import (
    ToolExposurePlan,
    ToolOrchestrator,
    apply_tool_exposure_allowlist,
    build_default_tool_exposure_plan,
    compile_tool_exposure_provider_schema,
)


def _tool(
    name: str,
    *,
    tags: tuple[str, ...] = (),
    is_capability_bridge: bool = False,
    concurrency_safe: bool = True,
) -> AIToolSpec:
    return AIToolSpec(
        name=name,
        description=f"{name} description",
        read_only=True,
        concurrency_safe=concurrency_safe,
        tags=tags,
        is_capability_bridge=is_capability_bridge,
    )


def test_default_tool_exposure_categories_are_stable_and_schema_free() -> None:
    plan = build_default_tool_exposure_plan(
        allowed_tools=(
            _tool("memory.query", tags=("memory",)),
            _tool("future_task.create", tags=("future_task",)),
            _tool("relationship.inspect", tags=("relationship",)),
            _tool(
                "plugin.capability.invoke",
                tags=("plugin_capability",),
                is_capability_bridge=True,
            ),
        ),
        ordinary_ambient_group=True,
    )

    assert plan.category_ids == (
        "memory",
        "future_task",
        "relationship",
        "plugin_capability",
    )
    assert "memory.query" not in plan.awareness_text
    assert "future_task.create" not in plan.awareness_text
    assert plan.selected_tools == ()
    assert plan.diagnostics["category_count"] == 4


def test_ambient_group_excludes_admin_project_management_tools() -> None:
    plan = build_default_tool_exposure_plan(
        allowed_tools=(
            _tool("memory.query", tags=("memory",)),
            _tool("admin.project.reload", tags=("admin", "project_management")),
        ),
        ordinary_ambient_group=True,
    )

    assert plan.category_ids == (
        "memory",
        "future_task",
        "relationship",
        "plugin_capability",
    )
    assert plan.hidden_reasons == {
        "admin.project.reload": "excluded_from_ambient_group"
    }
    assert plan.selected_tools == ()


def test_non_ambient_context_keeps_admin_diagnostics_visible() -> None:
    plan = build_default_tool_exposure_plan(
        allowed_tools=(
            _tool("admin.project.reload", tags=("admin", "project_management")),
        ),
        ordinary_ambient_group=False,
    )

    assert plan.hidden_reasons == {}
    assert plan.diagnostics["admin_project_tool_count"] == 1


def test_tool_orchestrator_selects_policy_allowed_executable_tools() -> None:
    orchestrator = ToolOrchestrator()

    plan = orchestrator.plan_exposure(
        allowed_tools=(
            _tool("memory.query", tags=("memory",)),
            _tool("memory.update", tags=("memory",)),
        ),
        policy=AIToolPolicy(
            execution_enabled=True,
            allowed_tool_names={"memory.query", "memory.update"},
            denied_tool_names={"memory.update"},
        ),
        requested_tool_names=("memory.query", "memory.update"),
        ordinary_ambient_group=False,
        execution_timeout_seconds=7.5,
    )

    assert tuple(tool.name for tool in plan.selected_tool_specs) == ("memory.query",)
    assert plan.selected_tools == ()
    provider_tools = compile_tool_exposure_provider_schema(plan)
    assert tuple(tool.name for tool in provider_tools) == ("memory_query",)
    assert plan.denied_reasons == {"memory.update": "policy_denied"}
    assert plan.unavailable_reasons == {}
    assert plan.diagnostics["execution_timeout_seconds"] == 7.5
    assert plan.diagnostics["parallel_safe_tool_names"] == ("memory.query",)


def test_tool_orchestrator_denial_observation_is_bounded() -> None:
    observation = ToolOrchestrator().build_denial_observation(
        tool_name="memory.update",
        reason="policy_denied",
    )

    assert "memory.update" in observation.content
    assert "policy_denied" in observation.content
    assert observation.truncated is False


def test_tool_orchestrator_does_not_assume_parallel_safety() -> None:
    plan = ToolOrchestrator().plan_exposure(
        allowed_tools=(
            _tool("memory.query", tags=("memory",), concurrency_safe=False),
        ),
        policy=AIToolPolicy(
            execution_enabled=True,
            allowed_tool_names={"memory.query"},
        ),
        requested_tool_names=("memory.query",),
        ordinary_ambient_group=False,
        execution_timeout_seconds=7.5,
    )

    assert tuple(tool.name for tool in plan.selected_tool_specs) == ("memory.query",)
    assert compile_tool_exposure_provider_schema(plan)[0].name == "memory_query"
    assert plan.diagnostics["parallel_safe_tool_names"] == ()


def test_tool_orchestrator_records_unavailable_tools_before_schema_compile() -> None:
    plan = ToolOrchestrator().plan_exposure(
        allowed_tools=(_tool("memory.query", tags=("memory",)),),
        policy=AIToolPolicy(
            execution_enabled=False,
            allowed_tool_names={"memory.query"},
        ),
        requested_tool_names=("memory.query",),
        ordinary_ambient_group=False,
        execution_timeout_seconds=3.0,
    )

    assert plan.selected_tool_specs == ()
    assert compile_tool_exposure_provider_schema(plan) == ()
    assert plan.unavailable_reasons == {"memory.query": "execution_disabled"}
    assert plan.diagnostics["selected_tool_count"] == 0
    assert plan.diagnostics["execution_timeout_seconds"] == 3.0


def test_tool_exposure_allowlist_uses_selected_tools_only() -> None:
    selected_tool = AIModelToolDefinition(
        name="memory_query",
        description="Recall memory",
        parameters={"type": "object", "properties": {}},
    )
    hidden_tool = AIModelToolDefinition(
        name="admin_project_reload",
        description="Reload project",
        parameters={"type": "object", "properties": {}},
    )
    request = ToolGatewayRequest(
        session_id="session-1",
        source_message_id="msg-1",
        trace_id="trace-1",
        message_text="hello",
        policy=AIToolPolicy(execution_enabled=True),
        recalled_memories=(),
        relationship_context=None,
        current_time=datetime(2026, 4, 29, tzinfo=timezone.utc),
    )
    plan = ToolExposurePlan(
        selected_tools=(selected_tool,),
        hidden_reasons={hidden_tool.name: "excluded_from_ambient_group"},
    )
    constrained = apply_tool_exposure_allowlist(request, plan)

    assert constrained.executable_tool_names == frozenset({"memory.query"})

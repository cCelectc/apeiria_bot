# ruff: noqa: PLR2004

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType

from apeiria.ai.capabilities import (
    AICapabilityBindingSnapshot,
    AICapabilityContract,
    AICapabilityContractSnapshot,
    AICapabilityKind,
    AICapabilityOrigin,
    AICapabilitySafety,
    create_local_tool_binding,
)
from apeiria.ai.model import AIModelToolDefinition
from apeiria.ai.tools import AIToolPolicy
from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopInput
from apeiria.app.ai.runtime.planning.tool_exposure import (
    ToolExposurePlan,
    ToolOrchestrator,
    apply_tool_exposure_allowlist,
    build_default_tool_exposure_plan,
    compile_tool_exposure_provider_schema,
)
from tests.ai.agent_turn_helpers import selected_model


def _tool(
    name: str,
    *,
    tags: tuple[str, ...] = (),
    safe: bool = True,
    risk_level: str = "low",
    input_schema: dict[str, object] | None = None,
) -> AICapabilityContract:
    return AICapabilityContract(
        name=name,
        kind=AICapabilityKind.EXECUTABLE,
        origin=AICapabilityOrigin.BUILTIN,
        description=f"{name} description",
        input_schema=input_schema or {},
        safety=AICapabilitySafety(
            read_only=risk_level == "low",
            risk_level=risk_level,  # type: ignore[arg-type]
            concurrency_safe=safe,
        ),
        tags=tags,
    )


async def _handler(**_: object) -> object:
    return {}


def _snapshots(
    tools: tuple[AICapabilityContract, ...],
) -> tuple[AICapabilityContractSnapshot, AICapabilityBindingSnapshot]:
    bindings = tuple(
        create_local_tool_binding(
            contract_name=tool.name,
            binding_key=f"local:{tool.name}",
            handler=_handler,
        )
        for tool in tools
    )
    return (
        AICapabilityContractSnapshot(
            contracts=tools,
            by_name=MappingProxyType({tool.name: tool for tool in tools}),
        ),
        AICapabilityBindingSnapshot(
            bindings=bindings,
            by_key=MappingProxyType(
                {binding.binding_key: binding for binding in bindings}
            ),
            by_contract=MappingProxyType(
                {binding.contract_name: binding for binding in bindings}
            ),
        ),
    )


def test_default_tool_exposure_categories_are_stable_and_schema_free() -> None:
    plan = build_default_tool_exposure_plan(
        allowed_tools=(
            _tool("memory.query", tags=("memory",)),
            _tool("future_task.create", tags=("future_task",)),
            _tool("relationship.inspect", tags=("relationship",)),
            _tool("plugin.inspect", tags=("plugin_capability",)),
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

    tools = (
        _tool("memory.query", tags=("memory",)),
        _tool("memory.update", tags=("memory",)),
    )
    contracts, bindings = _snapshots(tools)
    plan = orchestrator.plan_exposure(
        allowed_tools=tools,
        contracts=contracts,
        bindings=bindings,
        policy=AIToolPolicy(
            execution_enabled=True,
            allowed_tool_names={"memory.query", "memory.update"},
            denied_tool_names={"memory.update"},
        ),
        requested_tool_names=("memory.query", "memory.update"),
        ordinary_ambient_group=False,
        execution_timeout_seconds=7.5,
    )

    assert tuple(tool.name for tool in plan.selected_tool_contracts) == (
        "memory.query",
    )
    assert plan.selected_tools == ()
    provider_tools = compile_tool_exposure_provider_schema(plan)
    assert tuple(tool.name for tool in provider_tools) == ("memory_query",)
    assert plan.denied_reasons == {"memory.update": "explicitly denied"}
    assert plan.unavailable_reasons == {}
    assert plan.diagnostics["execution_timeout_seconds"] == 7.5
    assert plan.diagnostics["parallel_safe_tool_names"] == ("memory.query",)


def test_tool_exposure_plan_carries_capability_contract_projection() -> None:
    tool = _tool(
        "future_task.manage",
        risk_level="medium",
        safe=False,
        input_schema={
            "type": "object",
            "properties": {"title": {"type": "string", "description": "Task title"}},
            "required": ["title"],
            "additionalProperties": False,
        },
    )
    contracts, bindings = _snapshots((tool,))
    plan = ToolOrchestrator().plan_exposure(
        allowed_tools=(tool,),
        contracts=contracts,
        bindings=bindings,
        policy=AIToolPolicy(
            execution_enabled=True,
            allowed_tool_names={"future_task.manage"},
        ),
        requested_tool_names=("future_task.manage",),
        ordinary_ambient_group=False,
        execution_timeout_seconds=7.5,
        current_time=datetime(2026, 5, 7, tzinfo=timezone.utc),
    )

    assert tuple(plan.capability_plan.binding_map) == ("future_task.manage",)
    provider_tool = compile_tool_exposure_provider_schema(
        plan,
        current_time=datetime(2026, 5, 7, tzinfo=timezone.utc),
    )[0]
    assert provider_tool.name == "future_task_manage"
    assert provider_tool.parameters["required"] == ["title"]
    assert "Current reference time" in provider_tool.description
    assert plan.capability_contracts is not None
    assert plan.capability_bindings is not None
    assert "future_task.manage" in plan.capability_contracts.by_name
    assert "local:future_task.manage" in plan.capability_bindings.by_key


def test_tool_orchestrator_denial_observation_is_bounded() -> None:
    observation = ToolOrchestrator().build_denial_observation(
        tool_name="memory.update",
        reason="policy_denied",
    )

    assert "memory.update" in observation.content
    assert "policy_denied" in observation.content
    assert observation.truncated is False


def test_tool_orchestrator_does_not_assume_parallel_safety() -> None:
    tools = (_tool("memory.query", tags=("memory",), safe=False),)
    contracts, bindings = _snapshots(tools)
    plan = ToolOrchestrator().plan_exposure(
        allowed_tools=tools,
        contracts=contracts,
        bindings=bindings,
        policy=AIToolPolicy(
            execution_enabled=True,
            allowed_tool_names={"memory.query"},
        ),
        requested_tool_names=("memory.query",),
        ordinary_ambient_group=False,
        execution_timeout_seconds=7.5,
    )

    assert tuple(tool.name for tool in plan.selected_tool_contracts) == (
        "memory.query",
    )
    assert compile_tool_exposure_provider_schema(plan)[0].name == "memory_query"
    assert plan.diagnostics["parallel_safe_tool_names"] == ()


def test_tool_orchestrator_records_unavailable_tools_before_schema_compile() -> None:
    tools = (_tool("memory.query", tags=("memory",)),)
    contracts, bindings = _snapshots(tools)
    plan = ToolOrchestrator().plan_exposure(
        allowed_tools=tools,
        contracts=contracts,
        bindings=bindings,
        policy=AIToolPolicy(
            execution_enabled=False,
            allowed_tool_names={"memory.query"},
        ),
        requested_tool_names=("memory.query",),
        ordinary_ambient_group=False,
        execution_timeout_seconds=3.0,
    )

    assert plan.selected_tool_contracts == ()
    assert compile_tool_exposure_provider_schema(plan) == ()
    assert plan.unavailable_reasons == {"memory.query": "execution is disabled"}
    assert plan.diagnostics["selected_tool_count"] == 0
    assert plan.diagnostics["execution_timeout_seconds"] == 3.0


def test_tool_orchestrator_filters_contracts_by_selected_model_capability() -> None:
    tools = (_tool("memory.query", tags=("memory",)),)
    contracts, bindings = _snapshots(tools)
    plan = ToolOrchestrator().plan_exposure(
        allowed_tools=tools,
        contracts=contracts,
        bindings=bindings,
        policy=AIToolPolicy(
            execution_enabled=True,
            allowed_tool_names={"memory.query"},
        ),
        requested_tool_names=("memory.query",),
        ordinary_ambient_group=False,
        execution_timeout_seconds=3.0,
        model_supports_tools=False,
    )

    assert plan.selected_tool_contracts == tools
    assert compile_tool_exposure_provider_schema(plan) == ()
    assert plan.capability_plan.binding_map == {}
    assert plan.unavailable_reasons == {
        "memory.query": "selected model does not support tools"
    }
    assert plan.diagnostics["model_supports_tools"] is False


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
    request = RuntimeToolLoopInput(
        session_id="session-1",
        source_message_id="msg-1",
        trace_id="trace-1",
        runtime_mode="message",
        message_text="hello",
        current_time=datetime(2026, 4, 29, tzinfo=timezone.utc),
        selected=selected_model("tool-exposure"),
        fallback_models=(),
        messages=(),
        tools=(selected_tool, hidden_tool),
        tool_policy=AIToolPolicy(execution_enabled=True),
        executable_tool_names=None,
        recalled_memory_ids=(),
        recalled_memory_contents=(),
        relationship_context=None,
    )
    plan = ToolExposurePlan(
        selected_tools=(selected_tool,),
        hidden_reasons={hidden_tool.name: "excluded_from_ambient_group"},
    )
    constrained = apply_tool_exposure_allowlist(request, plan)

    assert constrained.executable_tool_names == frozenset({"memory.query"})

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path


def test_tool_level_ordering_and_policy_decision() -> None:
    from apeiria.ai.tools.models import (
        AIToolDefinition,
        AIToolLevel,
        AIToolPolicy,
        AIToolReadiness,
    )
    from apeiria.ai.tools.policy import evaluate_tool_policy

    async def _executor(**_: Any) -> object:
        return object()

    tool = AIToolDefinition(
        name="memory.update",
        description="update memory",
        input_schema={"type": "object", "properties": {}},
        required_level=AIToolLevel.WRITE,
        executor=_executor,
        readiness=AIToolReadiness.available(),
    )

    denied = evaluate_tool_policy(tool, AIToolPolicy(allowed_level=AIToolLevel.READ))
    allowed = evaluate_tool_policy(tool, AIToolPolicy(allowed_level=AIToolLevel.WRITE))

    assert denied.allowed is False
    assert denied.reason == "requires write, scene allows read"
    assert allowed.allowed is True


def test_tool_registry_rejects_duplicates_and_snapshots_are_immutable() -> None:
    from apeiria.ai.tools.models import AIToolDefinition, AIToolLevel, AIToolReadiness
    from apeiria.ai.tools.registry import AIDuplicateToolError, AIToolRegistry

    async def _executor(**_: Any) -> object:
        return object()

    tool = AIToolDefinition(
        name="relationship.inspect",
        description="inspect relationship",
        input_schema={"type": "object", "properties": {}},
        required_level=AIToolLevel.READ,
        executor=_executor,
        readiness=AIToolReadiness.available(),
    )
    registry = AIToolRegistry()
    registry.register(tool)
    registry.register(tool)

    with pytest.raises(AIDuplicateToolError):
        registry.register(
            AIToolDefinition(
                name="relationship.inspect",
                description="different implementation",
                input_schema={"type": "object", "properties": {}},
                required_level=AIToolLevel.READ,
                executor=_executor,
                readiness=AIToolReadiness.available(),
            )
        )

    snapshot = registry.snapshot()
    assert snapshot.tools == (tool,)
    with pytest.raises(TypeError):
        snapshot.by_name["relationship.inspect"] = tool  # type: ignore[index]


def test_tool_registry_rejects_unsupported_canonical_schemas() -> None:
    from apeiria.ai.tools.models import AIToolDefinition, AIToolLevel, AIToolReadiness
    from apeiria.ai.tools.registry import AIInvalidToolSchemaError, AIToolRegistry

    async def _executor(**_: Any) -> object:
        return object()

    registry = AIToolRegistry()

    with pytest.raises(AIInvalidToolSchemaError, match="root schema must be object"):
        registry.register(
            AIToolDefinition(
                name="bad.root",
                description="bad root",
                input_schema={"type": "string"},
                required_level=AIToolLevel.READ,
                executor=_executor,
                readiness=AIToolReadiness.available(),
            )
        )

    with pytest.raises(AIInvalidToolSchemaError, match="oneOf"):
        registry.register(
            AIToolDefinition(
                name="bad.combinator",
                description="bad combinator",
                input_schema={
                    "type": "object",
                    "properties": {
                        "value": {"oneOf": [{"type": "string"}, {"type": "number"}]}
                    },
                },
                required_level=AIToolLevel.READ,
                executor=_executor,
                readiness=AIToolReadiness.available(),
            )
        )


def test_tool_readiness_result_codes_are_explicit() -> None:
    from apeiria.ai.tools.models import AIToolReadiness

    assert AIToolReadiness.available().ready is True
    for code in (
        "disabled",
        "plugin_unavailable",
        "runtime_missing_capability",
        "missing_executor",
        "approval_missing",
    ):
        readiness = AIToolReadiness.not_ready(code, f"{code} reason")
        assert readiness.ready is False
        assert readiness.code == code
        assert readiness.reason == f"{code} reason"


def test_builtin_tools_register_with_levels_and_nonmanageable_defaults() -> None:
    from apeiria.ai.tools.models import AIToolLevel
    from apeiria.ai.tools.service import AIToolService

    service = AIToolService()
    assert service.registry.register_pending_tools() == 0
    tools = {tool.name: tool for tool in service.list_tool_specs()}

    assert tools["memory.query"].required_level is AIToolLevel.READ
    assert tools["relationship.inspect"].required_level is AIToolLevel.READ
    assert tools["memory.update"].required_level is AIToolLevel.WRITE
    assert tools["future_task.manage"].required_level is AIToolLevel.WRITE
    assert all(tool.origin == "builtin" for tool in tools.values())
    assert all(tool.manageable is False for tool in tools.values())


def test_tool_exposure_plan_filters_by_model_support_readiness_and_level() -> None:
    from apeiria.ai.tools.exposure import create_tool_exposure_plan
    from apeiria.ai.tools.models import (
        AIToolDefinition,
        AIToolLevel,
        AIToolPolicy,
        AIToolReadiness,
    )

    async def _executor(**_: Any) -> object:
        return object()

    ready_read = AIToolDefinition(
        name="memory.query",
        description="read",
        input_schema={"type": "object", "properties": {}},
        required_level=AIToolLevel.READ,
        executor=_executor,
        readiness=AIToolReadiness.available(),
    )
    host_tool = AIToolDefinition(
        name="browser.open",
        description="host",
        input_schema={"type": "object", "properties": {}},
        required_level=AIToolLevel.HOST,
        executor=_executor,
        readiness=AIToolReadiness.available(),
    )
    unavailable = AIToolDefinition(
        name="plugin.echo",
        description="plugin",
        input_schema={"type": "object", "properties": {}},
        required_level=AIToolLevel.READ,
        executor=_executor,
        readiness=AIToolReadiness.not_ready(
            "plugin_unavailable",
            "plugin is disabled",
        ),
    )

    plan = create_tool_exposure_plan(
        tools=(ready_read, host_tool, unavailable),
        policy=AIToolPolicy(allowed_level=AIToolLevel.READ),
        model_supports_tools=True,
    )

    assert plan.visible_tools == (ready_read,)
    assert plan.denied_reasons == {"browser.open": "requires host, scene allows read"}
    assert plan.unavailable_reasons == {"plugin.echo": "plugin is disabled"}
    assert plan.diagnostics["browser.open"].required_level is AIToolLevel.HOST
    assert plan.diagnostics["browser.open"].allowed_level is AIToolLevel.READ
    assert plan.diagnostics["plugin.echo"].readiness_code == "plugin_unavailable"

    unsupported = create_tool_exposure_plan(
        tools=(ready_read,),
        policy=AIToolPolicy(allowed_level=AIToolLevel.ADMIN),
        model_supports_tools=False,
    )

    assert unsupported.visible_tools == ()
    assert unsupported.unavailable_reasons == {
        "memory.query": "model does not support tool calling"
    }
    assert unsupported.diagnostics["memory.query"].unsupported_model_reason == (
        "model does not support tool calling"
    )


def test_provider_tool_projection_uses_safe_names_and_provider_payloads() -> None:
    from apeiria.ai.tools.models import AIToolDefinition, AIToolLevel
    from apeiria.ai.tools.projection import (
        project_tools_for_anthropic,
        project_tools_for_gemini,
        project_tools_for_openai,
    )

    async def _executor(**_: Any) -> object:
        return object()

    tool = AIToolDefinition(
        name="future_task.manage",
        description="manage reminders",
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "cancel", "list"],
                    "description": "operation",
                }
            },
            "required": ["action"],
            "additionalProperties": False,
        },
        required_level=AIToolLevel.WRITE,
        executor=_executor,
    )

    openai_projection = project_tools_for_openai((tool,))
    anthropic_projection = project_tools_for_anthropic((tool,))
    gemini_projection = project_tools_for_gemini((tool,))

    assert openai_projection.name_map == {"future_task_manage": "future_task.manage"}
    assert openai_projection.payloads == (
        {
            "type": "function",
            "function": {
                "name": "future_task_manage",
                "description": "manage reminders",
                "parameters": tool.input_schema,
                "strict": True,
            },
        },
    )
    assert anthropic_projection.payloads == (
        {
            "name": "future_task_manage",
            "description": "manage reminders",
            "input_schema": tool.input_schema,
        },
    )
    assert gemini_projection.payloads == (
        {
            "name": "future_task_manage",
            "description": "manage reminders",
            "parameters": tool.input_schema,
        },
    )
    assert gemini_projection.resolve_provider_name("future_task_manage") == (
        "future_task.manage"
    )


def test_tool_call_intents_use_provider_name_mapping() -> None:
    from apeiria.ai.model.runtime.adapter import AIModelToolCall
    from apeiria.ai.tools.function_calling import build_intents_from_tool_calls

    intents = build_intents_from_tool_calls(
        (
            AIModelToolCall(
                tool_call_id="call-1",
                name="future_task_manage",
                arguments={"action": "list"},
            ),
        ),
        provider_name_map={"future_task_manage": "future_task.manage"},
    )

    assert intents[0].tool_name == "future_task.manage"
    assert intents[0].call_id == "call-1"


def test_tool_execution_rechecks_policy_and_records_denials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.tools.models import (
        AIToolDefinition,
        AIToolExecutionRequest,
        AIToolIntent,
        AIToolLevel,
        AIToolPolicy,
        AIToolReadiness,
        AIToolResult,
    )
    from apeiria.ai.tools.service import AIToolService

    with database_runtime.connect_sync() as connection:
        connection.execute(
            """
            INSERT INTO chat_session (
                session_id,
                platform,
                bot_id,
                scene_type,
                scene_id,
                created_at,
                updated_at,
                last_message_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "session-1",
                "console",
                "bot",
                "private",
                "user-1",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )

    async def _executor(**_: Any) -> AIToolResult:
        return AIToolResult(summary="- [admin.run] should not run")

    service = AIToolService()
    service.registry.register(
        AIToolDefinition(
            name="admin.run",
            description="admin",
            input_schema={"type": "object", "properties": {}},
            required_level=AIToolLevel.ADMIN,
            executor=_executor,
            readiness=AIToolReadiness.available(),
        )
    )
    service.registry.register(
        AIToolDefinition(
            name="plugin.echo",
            description="plugin",
            input_schema={"type": "object", "properties": {}},
            required_level=AIToolLevel.READ,
            executor=_executor,
            readiness=AIToolReadiness.not_ready(
                "plugin_unavailable",
                "plugin disabled",
            ),
        )
    )

    async def scenario() -> None:
        observations = await service.execute_tool_intents(
            request=AIToolExecutionRequest(
                session_id="session-1",
                source_message_id=None,
                trace_id="trace-1",
                message_text="run",
                policy=AIToolPolicy(allowed_level=AIToolLevel.READ),
                recalled_memory_ids=(),
                recalled_memory_contents=(),
                relationship_context=None,
            ),
            intents=[
                AIToolIntent(
                    tool_name="admin.run",
                    kind="invoke_tool",
                    input_payload={},
                    call_id="call-denied",
                ),
                AIToolIntent(
                    tool_name="plugin.echo",
                    kind="invoke_tool",
                    input_payload={},
                    call_id="call-not-ready",
                ),
            ],
        )
        rows = await service.list_executions(session_id="session-1")

        assert [item.status for item in observations] == ["denied", "not_ready"]
        assert [row.status for row in rows] == ["denied", "not_ready"]
        assert rows[0].call_id == "call-denied"
        assert rows[0].reason == "requires admin, scene allows read"
        assert rows[1].call_id == "call-not-ready"
        assert rows[1].reason == "plugin disabled"

    asyncio.run(scenario())


def test_gemini_adapter_projects_tools_to_function_declarations() -> None:
    from apeiria.ai.model.adapters.gemini_native import _build_gemini_generate_payload
    from apeiria.ai.model.runtime.adapter import AIModelToolDefinition

    payload = _build_gemini_generate_payload(
        prompt="hello",
        messages=(),
        tools=(
            AIModelToolDefinition(
                name="memory_query",
                description="inspect memory",
                parameters={"type": "object", "properties": {}},
            ),
        ),
        temperature=None,
        max_tokens=None,
        options={},
    )

    assert payload["tools"] == [
        {
            "functionDeclarations": [
                {
                    "name": "memory_query",
                    "description": "inspect memory",
                    "parameters": {"type": "object", "properties": {}},
                }
            ]
        }
    ]


def test_tool_policy_bindings_store_allowed_level(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.tools.models import AIToolLevel
    from apeiria.ai.tools.policy import (
        AIToolPolicyBindingCreateInput,
        AIToolPolicyBindingTarget,
        AIToolSceneContext,
        ai_tool_policy_binding_service,
    )

    async def scenario() -> None:
        await ai_tool_policy_binding_service.create_binding(
            AIToolPolicyBindingCreateInput(
                scope_type="global",
                scope_id="__global__",
                allowed_level=AIToolLevel.READ,
            )
        )
        group = await ai_tool_policy_binding_service.create_binding(
            AIToolPolicyBindingCreateInput(
                scope_type="group",
                scope_id="group-1",
                allowed_level=AIToolLevel.WRITE,
            )
        )
        user = await ai_tool_policy_binding_service.create_binding(
            AIToolPolicyBindingCreateInput(
                scope_type="user",
                scope_id="user-1",
                allowed_level=AIToolLevel.HOST,
            )
        )

        resolved = await ai_tool_policy_binding_service.resolve_scene_policy(
            scene_context=AIToolSceneContext(scope_type="private", is_tome=False),
            target=AIToolPolicyBindingTarget(
                conversation_id="conv-1",
                group_id="group-1",
                user_id="user-1",
            ),
        )

        assert resolved.allowed_level is AIToolLevel.HOST

        updated = await ai_tool_policy_binding_service.update_binding(
            binding_id=user.binding_id,
            allowed_level=AIToolLevel.ADMIN,
        )
        assert updated is not None
        assert updated.allowed_level is AIToolLevel.ADMIN

        deleted = await ai_tool_policy_binding_service.delete_binding(
            binding_id=user.binding_id
        )
        assert deleted is True

        fallback = await ai_tool_policy_binding_service.resolve_scene_policy(
            scene_context=AIToolSceneContext(scope_type="private", is_tome=False),
            target=AIToolPolicyBindingTarget(
                conversation_id="conv-1",
                group_id="group-1",
                user_id="user-1",
            ),
        )
        assert fallback.allowed_level is AIToolLevel.WRITE
        binding_levels = [
            item.allowed_level
            for item in await ai_tool_policy_binding_service.list_bindings()
        ]
        assert binding_levels == [
            AIToolLevel.READ,
            group.allowed_level,
        ]

    asyncio.run(scenario())


def test_tool_observation_records_support_denied_and_not_ready(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.tools.contracts import AIToolObservationCreateInput
    from apeiria.ai.tools.execution_repository import AIToolExecutionRepository

    with database_runtime.connect_sync() as connection:
        connection.execute(
            """
            INSERT INTO chat_session (
                session_id,
                platform,
                bot_id,
                scene_type,
                scene_id,
                created_at,
                updated_at,
                last_message_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "session-1",
                "console",
                "bot",
                "private",
                "user-1",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )

    repository = AIToolExecutionRepository()
    denied = repository.record_observation(
        AIToolObservationCreateInput(
            session_id="session-1",
            tool_name="shell.run",
            status="denied",
            reason="requires admin, scene allows host",
            trace_id="trace-1",
            call_id="call-1",
            input_payload={"command": "pwd"},
            output_payload={"error": "denied"},
        )
    )
    not_ready = repository.record_observation(
        AIToolObservationCreateInput(
            session_id="session-1",
            tool_name="browser.open",
            status="not_ready",
            reason="runtime missing browser capability",
        )
    )

    rows = repository.list_executions(session_id="session-1")

    assert denied.status == "denied"
    assert denied.reason == "requires admin, scene allows host"
    assert not_ready.status == "not_ready"
    assert [row.status for row in rows] == ["denied", "not_ready"]

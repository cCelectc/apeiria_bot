from __future__ import annotations

import asyncio
import importlib.util
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from apeiria.ai.tools import (
    AIToolDefinition,
    AIToolExecutionContext,
    AIToolExecutionRequest,
    AIToolIntent,
    AIToolLevel,
    AIToolPolicy,
    AIToolReadiness,
    AIToolResult,
)
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


INTERNAL_TOOL_NAMES = (
    "future_task.cancel",
    "future_task.create",
    "future_task.list",
    "knowledge.search",
    "memory.search",
    "memory.write",
    "relationship.inspect",
)
HTTP_OK = 200
HTTP_NOT_FOUND = 404
KNOWLEDGE_CANDIDATE_COUNT = 20
KNOWLEDGE_EXCERPT_LIMIT = 320
KNOWLEDGE_RESULT_LIMIT = 5
TOOL_GUIDANCE_LIMIT = 900


def test_internal_tools_contribute_idempotently_and_deterministically() -> None:
    from apeiria.ai.contributions import AIContributionRegistry
    from apeiria.ai.tools.registry import AIToolRegistry
    from apeiria.app.ai.builtin_tools import register_internal_tools

    contributions = AIContributionRegistry()
    registry = AIToolRegistry()

    register_internal_tools(contributions)
    register_internal_tools(contributions)
    for contribution in contributions.snapshot().tools:
        registry.register(contribution.tool)

    assert tuple(tool.name for tool in registry.snapshot().tools) == INTERNAL_TOOL_NAMES

    tools = registry.snapshot().by_name
    assert tools["memory.search"].required_level is AIToolLevel.READ
    assert tools["memory.write"].required_level is AIToolLevel.WRITE
    assert tools["knowledge.search"].required_level is AIToolLevel.READ
    assert tools["future_task.create"].required_level is AIToolLevel.WRITE
    assert tools["future_task.list"].required_level is AIToolLevel.READ
    assert tools["future_task.cancel"].required_level is AIToolLevel.WRITE
    assert tools["relationship.inspect"].required_level is AIToolLevel.READ
    assert all(tool.origin == "internal" for tool in tools.values())
    assert all(tool.manageable is False for tool in tools.values())


def test_internal_tool_package_uses_decorated_handlers() -> None:
    from apeiria.app.ai import builtin_tools
    from apeiria.app.ai.builtin_tools import common, future_tasks, knowledge, memory

    assert not hasattr(builtin_tools, "build_internal_tools")
    assert not hasattr(builtin_tools, "INTERNAL_TOOLS")
    assert not hasattr(memory, "build_memory_tools")
    assert not hasattr(knowledge, "build_knowledge_tools")
    assert not hasattr(future_tasks, "build_future_task_tools")
    assert hasattr(memory.search_memory, "__ai_tool_definition__")
    assert hasattr(knowledge.search_knowledge, "__ai_tool_definition__")
    assert hasattr(future_tasks.create_future_task, "__ai_tool_definition__")
    assert not hasattr(common, "object_schema")
    assert not hasattr(common, "string_schema")
    assert not hasattr(common, "integer_schema")
    assert not hasattr(common, "number_schema")


def test_internal_tools_exclude_host_level_tools() -> None:
    from apeiria.ai.contributions import AIContributionRegistry
    from apeiria.ai.tools.registry import AIToolRegistry
    from apeiria.app.ai.builtin_tools import register_internal_tools

    contributions = AIContributionRegistry()
    registry = AIToolRegistry()
    register_internal_tools(contributions)
    for contribution in contributions.snapshot().tools:
        registry.register(contribution.tool)

    forbidden_fragments = (
        "shell",
        "python",
        "browser",
        "file",
        "filesystem",
        "computer",
    )
    for tool in registry.snapshot().tools:
        searchable = f"{tool.name} {tool.description}".lower()
        assert tool.required_level not in {AIToolLevel.HOST, AIToolLevel.ADMIN}
        assert not any(fragment in searchable for fragment in forbidden_fragments)


def test_builtin_catalog_apis_are_removed() -> None:
    from apeiria.ai.tools.registry import AIToolRegistry

    assert importlib.util.find_spec("apeiria.ai.tools.catalog") is None
    assert importlib.util.find_spec("apeiria.ai.tools.essential") is None
    assert not hasattr(AIToolRegistry(), "load_builtin_catalog")


def test_lifecycle_registers_internal_and_plugin_tools_in_one_loop() -> None:
    from apeiria.ai.contributions import AIContributionRegistry
    from apeiria.app.ai.lifecycle import AIPluginLifecycleCoordinator

    order: list[str] = []
    tool_service = _FakeToolService(order)
    skill_service = _FakeSkillService(order, tool_service)
    future_service = _FakeFutureTaskService(order)
    contributions = AIContributionRegistry()

    contributions.register_tool(tool=_plugin_tool("plugin.echo"))

    def app_loader(registry: AIContributionRegistry) -> int:
        from apeiria.app.ai.builtin_tools import register_internal_tools

        order.append("app_loader")
        return register_internal_tools(registry)

    coordinator = AIPluginLifecycleCoordinator(
        contribution_registry=contributions,
        tool_service=tool_service,
        skill_service=skill_service,
        future_task_service=future_service,
        app_tool_loader=app_loader,
    )

    snapshot = asyncio.run(coordinator.startup())
    asyncio.run(coordinator.startup())

    first_startup_order = order[: order.index("future_recovery") + 1]
    assert first_startup_order[0] == "app_loader"
    assert first_startup_order[-2:] == ["skills", "future_recovery"]
    assert set(first_startup_order[1:-2]) == {
        *[f"tool:{name}" for name in INTERNAL_TOOL_NAMES],
        "tool:plugin.echo",
    }
    assert "builtin_catalog" not in order
    assert "pending_tools" not in order
    assert skill_service.calls[0] == ()
    assert set(tool_service.registry.tools) == {*INTERNAL_TOOL_NAMES, "plugin.echo"}
    assert not hasattr(snapshot, "capabilities")
    assert all(
        "builtin_tools" not in component.detail for component in snapshot.components
    )
    assert future_service.calls == 1


def test_plugin_duplicate_with_internal_tool_is_rejected() -> None:
    from apeiria.ai.contributions import AIContributionRegistry
    from apeiria.app.ai.lifecycle import AIPluginLifecycleCoordinator

    contributions = AIContributionRegistry()
    contributions.register_tool(tool=_plugin_tool("memory.search"))
    tool_service = _FakeToolService([])

    def app_loader(registry: AIContributionRegistry) -> int:
        from apeiria.app.ai.builtin_tools import register_internal_tools

        return register_internal_tools(registry)

    coordinator = AIPluginLifecycleCoordinator(
        contribution_registry=contributions,
        tool_service=tool_service,
        skill_service=_FakeSkillService([], tool_service),
        future_task_service=_FakeFutureTaskService([]),
        app_tool_loader=app_loader,
    )

    snapshot = coordinator.ensure_runtime_support_initialized()

    assert snapshot.initialized is False
    assert snapshot.initialization_source == "failed"
    assert "AIDuplicateToolError" in snapshot.diagnostics[0]


def test_memory_search_facade_delegates_with_actor_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apeiria.ai.memory.models import AIMemoryQuery
    from apeiria.app.ai.builtin_tools import memory as memory_tools

    calls: list[AIMemoryQuery] = []

    class FakeMemoryService:
        async def retrieve_memories(self, query: AIMemoryQuery):
            calls.append(query)
            return [
                _memory_definition(
                    memory_id="mem-1",
                    anchor_type="user",
                    anchor_id="user-1",
                    content="prefers terse implementation notes",
                )
            ]

    monkeypatch.setattr(memory_tools, "ai_memory_service", FakeMemoryService())

    result = asyncio.run(
        memory_tools.search_memory(
            "implementation notes",
            limit=25,
            context=_tool_context(
                session_id="session-group",
                actor_id="user-1",
                chat_scope_type="group",
                chat_scope_id="group-1",
                reply_audience="group:group-1",
            ),
        )
    )

    assert calls == [
        AIMemoryQuery(
            anchor_type="user",
            anchor_id="user-1",
            query_text="implementation notes",
            limit=10,
            memory_layer=None,
            memory_kind=None,
        )
    ]
    assert result.status == "success"
    assert result.output_payload["context"]["actor_id"] == "user-1"
    assert result.output_payload["context"]["chat_scope_type"] == "group"
    assert result.output_payload["context"]["reply_audience"] == "group:group-1"
    assert result.output_payload["results"][0]["memory_id"] == "mem-1"


def test_memory_write_facade_normalizes_and_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apeiria.ai.memory.contracts import AIMemoryCreateInput
    from apeiria.app.ai.builtin_tools import memory as memory_tools

    calls: list[AIMemoryCreateInput] = []

    class FakeMemoryService:
        async def create_memory(self, create_input: AIMemoryCreateInput):
            calls.append(create_input)
            return _memory_definition(
                memory_id="mem-new",
                anchor_type=create_input.anchor_type,
                anchor_id=create_input.anchor_id,
                content=create_input.content,
            )

    monkeypatch.setattr(memory_tools, "ai_memory_service", FakeMemoryService())

    result = asyncio.run(
        memory_tools.write_memory(
            "  Likes deterministic tests.  ",
            memory_kind="invalid",
            salience=99,
            confidence=-1,
            context=_tool_context(actor_id="user-1"),
        )
    )

    assert calls == [
        AIMemoryCreateInput(
            anchor_type="user",
            anchor_id="user-1",
            memory_layer="long_term",
            memory_kind="note",
            content="Likes deterministic tests.",
            is_editable=True,
            source_message_id="message-1",
            salience=1.0,
            confidence=0.0,
        )
    ]
    assert result.output_payload["memory_id"] == "mem-new"


def test_knowledge_search_facade_delegates_and_bounds_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apeiria.ai.knowledge.models import (
        KnowledgeRetrievalDiagnostics,
        KnowledgeRetrievalItem,
        KnowledgeRetrievalResult,
    )
    from apeiria.app.ai.builtin_tools import knowledge as knowledge_tools

    calls: list[tuple[str, int]] = []

    class FakeKnowledgeService:
        async def retrieve(
            self,
            *,
            query_text: str,
            limit: int,
        ):
            calls.append((query_text, limit))
            return KnowledgeRetrievalResult(
                items=tuple(
                    KnowledgeRetrievalItem(
                        label=f"K{index}",
                        document_id=f"doc-{index}",
                        chunk_id=f"chunk-{index}",
                        title=f"Doc {index}",
                        source_file_name="doc.md",
                        rank=index,
                        score=0.5,
                        rerank_score=None,
                        excerpt="x" * 700,
                    )
                    for index in range(1, KNOWLEDGE_RESULT_LIMIT + 3)
                ),
                diagnostics=KnowledgeRetrievalDiagnostics(
                    candidate_count=KNOWLEDGE_CANDIDATE_COUNT,
                    selected_count=KNOWLEDGE_RESULT_LIMIT + 2,
                ),
            )

    monkeypatch.setattr(
        knowledge_tools,
        "knowledge_retrieval_service",
        FakeKnowledgeService(),
    )

    result = asyncio.run(
        knowledge_tools.search_knowledge(
            "Apeiria knowledge",
            limit=99,
            context=_tool_context(),
        )
    )

    assert calls == [("Apeiria knowledge", KNOWLEDGE_RESULT_LIMIT)]
    assert len(result.output_payload["items"]) == KNOWLEDGE_RESULT_LIMIT
    assert len(result.output_payload["items"][0]["excerpt"]) <= KNOWLEDGE_EXCERPT_LIMIT
    assert (
        result.output_payload["diagnostics"]["candidate_count"]
        == KNOWLEDGE_CANDIDATE_COUNT
    )


def test_future_task_facades_delegate_to_application_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import apeiria.conversation.service as conversation_service_module
    from apeiria.app.ai.builtin_tools import future_tasks as future_task_tools
    from apeiria.conversation.models import ChatSessionIdentity

    calls: list[tuple[str, object]] = []
    task = _future_task_definition(task_id="task-1")

    class FakeFutureTasksEntry:
        async def create_task(self, create_input: object):
            calls.append(("create", create_input))
            return type("CreateResult", (), {"task": task})()

        async def list_tasks(self, *, limit: int, session_id: str | None = None):
            calls.append(("list", (limit, session_id)))
            return [task]

        async def get_task(self, *, task_id: str):
            calls.append(("get", task_id))
            return task

        async def cancel_task(
            self,
            *,
            task_id: str,
            actor_username: str | None = None,
        ):
            calls.append(("cancel", (task_id, actor_username)))
            return task

    class FakeChatSessionService:
        async def get_session_identity(self, *, session_id: str):
            return ChatSessionIdentity(
                session_id=session_id,
                platform="onebot",
                bot_id="bot-1",
                scene_type="group",
                scene_id="group-1",
                subject_id="user-1",
            )

    monkeypatch.setattr(
        future_task_tools,
        "_resolve_future_tasks_entry",
        FakeFutureTasksEntry,
    )
    monkeypatch.setattr(
        conversation_service_module,
        "chat_session_service",
        FakeChatSessionService(),
    )

    context = _tool_context(
        session_id="session-group",
        actor_id="user-1",
        chat_scope_type="group",
        chat_scope_id="group-1",
        reply_audience="group:group-1",
    )
    create_result = asyncio.run(
        future_task_tools.create_future_task(
            description="Follow up",
            trigger_at="2026-05-15T09:00:00+08:00",
            context=context,
        )
    )
    list_result = asyncio.run(future_task_tools.list_future_tasks(context=context))
    cancel_result = asyncio.run(
        future_task_tools.cancel_future_task("task-1", context=context)
    )

    assert [call[0] for call in calls] == ["create", "list", "get", "cancel"]
    assert create_result.output_payload["task"]["task_id"] == "task-1"
    assert list_result.output_payload["tasks"][0]["task_id"] == "task-1"
    assert cancel_result.output_payload["task"]["status"] == "pending"


def test_essential_execution_context_propagates_group_chat_scope() -> None:
    from apeiria.ai.tools.execution import AIToolIntentExecutor
    from apeiria.ai.tools.registry import AIToolRegistry

    captured: list[AIToolExecutionContext] = []

    async def executor(*, context: AIToolExecutionContext) -> AIToolResult:
        captured.append(context)
        return AIToolResult(summary="- [memory.search] ok")

    registry = AIToolRegistry(
        (
            AIToolDefinition(
                name="memory.search",
                description="search",
                input_schema={"type": "object", "properties": {}},
                required_level=AIToolLevel.READ,
                executor=executor,
            ),
        )
    )

    observations = asyncio.run(
        AIToolIntentExecutor().execute_tool_intents(
            registry=registry,
            request=AIToolExecutionRequest(
                session_id="session-group",
                source_message_id="message-1",
                trace_id="trace-1",
                message_text="search",
                policy=AIToolPolicy(allowed_level=AIToolLevel.READ),
                recalled_memory_ids=(),
                recalled_memory_contents=(),
                relationship_context=None,
                actor_id="user-1",
                chat_scope_type="group",
                chat_scope_id="group-1",
                reply_audience="group:group-1",
            ),
            intents=[
                AIToolIntent(
                    tool_name="memory.search",
                    kind="observe_read_only",
                    input_payload={},
                )
            ],
        )
    )

    assert observations[0].status == "success"
    assert captured[0].actor_id == "user-1"
    assert captured[0].chat_scope_type == "group"
    assert captured[0].chat_scope_id == "group-1"
    assert captured[0].reply_audience == "group:group-1"


def test_prompt_tool_guidance_is_generated_from_selected_exposure_plan() -> None:
    from apeiria.ai.prompting.reply import (
        REPLY_SECTION_TOOL_GUIDANCE,
        ReplyPromptInput,
        build_reply_planner_packet,
    )
    from apeiria.app.ai.runtime.planning.tool_exposure import (
        ToolExposurePlan,
        build_tool_guidance_text,
    )

    async def handler(**_: Any) -> AIToolResult:
        return AIToolResult(summary="ok")

    selected = (
        AIToolDefinition(
            name="memory.search",
            description="Search selected memories only when compact context is stale.",
            input_schema={"type": "object", "properties": {}},
            required_level=AIToolLevel.READ,
            executor=handler,
            origin="internal",
        ),
        AIToolDefinition(
            name="plugin.echo",
            description="Echo one plugin-selected value.",
            input_schema={"type": "object", "properties": {}},
            required_level=AIToolLevel.READ,
            executor=handler,
            origin="plugin",
        ),
        AIToolDefinition(
            name="mcp.ticket.search",
            description="Search external MCP tickets selected for this scene.",
            input_schema={"type": "object", "properties": {}},
            required_level=AIToolLevel.READ,
            executor=handler,
            origin="mcp",
        ),
    )
    generated_guidance = build_tool_guidance_text(
        ToolExposurePlan(
            selected_tool_definitions=selected,
            provider_name_map={
                "memory_search": "memory.search",
                "plugin_echo": "plugin.echo",
                "mcp_ticket_search": "mcp.ticket.search",
            },
        )
    )

    packet = build_reply_planner_packet(
        ReplyPromptInput(
            persona=None,
            scene_type="private",
            relationship=None,
            tool_policy="allowed",
            tool_results=(),
            memories=(),
            turns=(),
            person_profile=(),
            tool_guidance=generated_guidance,
        )
    )
    guidance = next(
        section.content
        for section in packet.sections
        if section.name == REPLY_SECTION_TOOL_GUIDANCE
    )

    assert guidance == generated_guidance
    assert len(guidance) < TOOL_GUIDANCE_LIMIT
    assert "memory_search (memory.search, read)" in guidance
    assert "plugin_echo (plugin.echo, read)" in guidance
    assert "mcp_ticket_search (mcp.ticket.search, read)" in guidance
    assert "Echo one plugin-selected value." in guidance
    assert "Search external MCP tickets selected for this scene." in guidance
    assert "future_task.cancel" not in guidance


def test_tool_diagnostics_route_reports_internal_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from apeiria.webui.auth import require_control_panel
    from apeiria.webui.routes.ai import router

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    def dependency_override() -> object:
        return object()

    app = FastAPI()
    app.dependency_overrides[require_control_panel] = dependency_override
    app.include_router(router, prefix="/ai")
    client = TestClient(app)

    response = client.get("/ai/tools?allowed_level=read")

    assert response.status_code == HTTP_OK
    payload = {item["name"]: item for item in response.json()}
    assert payload["memory.search"]["origin"] == "internal"
    assert "tags" not in payload["memory.search"]
    assert payload["memory.search"]["status"] == "visible"
    assert payload["memory.search"]["required_level"] == "read"
    assert payload["memory.write"]["status"] == "denied"
    assert payload["memory.write"]["denied_reason"] == (
        "requires write, scene allows read"
    )
    assert payload["knowledge.search"]["readiness_code"] in {
        "ready",
        "runtime_missing_capability",
    }


def test_combined_capability_inventory_route_is_not_registered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from apeiria.webui.auth import require_control_panel
    from apeiria.webui.routes.ai import router

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    def dependency_override() -> object:
        return object()

    app = FastAPI()
    app.dependency_overrides[require_control_panel] = dependency_override
    app.include_router(router, prefix="/ai")
    client = TestClient(app)

    response = client.get("/ai/tools/capabilities")

    assert response.status_code == HTTP_NOT_FOUND


def _plugin_tool(name: str) -> AIToolDefinition:
    async def handler(**_: Any) -> AIToolResult:
        return AIToolResult(summary="ok")

    return AIToolDefinition(
        name=name,
        description=f"{name} description",
        input_schema={"type": "object", "properties": {}},
        required_level=AIToolLevel.READ,
        executor=handler,
        readiness=AIToolReadiness.available(),
        origin="plugin",
        manageable=True,
    )


class _FakeToolRegistry:
    def __init__(self, order: list[str]) -> None:
        self._order = order
        self.tools: dict[str, AIToolDefinition] = {}

    def register(self, tool: AIToolDefinition) -> None:
        from apeiria.ai.tools.registry import AIDuplicateToolError

        if tool.name in self.tools and self.tools[tool.name] is not tool:
            raise AIDuplicateToolError(tool.name)
        if tool.name not in self.tools:
            self._order.append(f"tool:{tool.name}")
            self.tools[tool.name] = tool

    def list_tools(self) -> list[AIToolDefinition]:
        return [self.tools[name] for name in sorted(self.tools)]


class _FakeToolService:
    def __init__(self, order: list[str]) -> None:
        self.registry = _FakeToolRegistry(order)


class _FakeSkillService:
    def __init__(self, order: list[str], tool_service: _FakeToolService) -> None:
        del tool_service
        self._order = order
        self.calls: list[tuple[Path, ...]] = []

    def ensure_initialized(
        self,
        *,
        skill_sources: tuple[Path, ...] = (),
    ) -> None:
        self._order.append("skills")
        self.calls.append(skill_sources)


class _FakeFutureTaskService:
    def __init__(self, order: list[str]) -> None:
        self._order = order
        self.calls = 0

    async def recover_scheduled_tasks(self) -> object:
        self.calls += 1
        self._order.append("future_recovery")
        return type(
            "RecoveryResult",
            (),
            {"rescheduled_task_ids": (), "failed_task_ids": ()},
        )()


def _tool_context(
    *,
    session_id: str = "session-1",
    actor_id: str | None = "user-1",
    chat_scope_type: str | None = "private",
    chat_scope_id: str | None = "user-1",
    reply_audience: str | None = "private:user-1",
) -> AIToolExecutionContext:
    return AIToolExecutionContext(
        session_id=session_id,
        source_message_id="message-1",
        trace_id="trace-1",
        message_text="hello",
        policy=AIToolPolicy(allowed_level=AIToolLevel.WRITE),
        recalled_memory_ids=(),
        recalled_memory_contents=(),
        relationship_context=None,
        execution_timeout_seconds=None,
        actor_id=actor_id,
        chat_scope_type=chat_scope_type,
        chat_scope_id=chat_scope_id,
        reply_audience=reply_audience,
    )


def _memory_definition(
    *,
    memory_id: str,
    anchor_type: str,
    anchor_id: str,
    content: str,
) -> object:
    from apeiria.ai.memory.models import AIMemoryDefinition

    return AIMemoryDefinition(
        memory_id=memory_id,
        anchor_type=anchor_type,  # type: ignore[arg-type]
        anchor_id=anchor_id,
        memory_layer="long_term",
        memory_kind="note",
        content=content,
        is_editable=True,
        lifecycle_state="active",
        default_use_mode="context",
        governance_reason=None,
        source_message_id="message-1",
        salience=0.7,
        confidence=0.8,
        last_recalled_at=None,
        created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )


def _future_task_definition(*, task_id: str) -> object:
    from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition

    now = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)
    return AIFutureTaskDefinition(
        task_id=task_id,
        session_id="session-group",
        platform="onebot",
        scene_type="group",
        scene_id="group-1",
        user_id="user-1",
        title="Follow up",
        description="Follow up",
        trigger_at=now,
        status="pending",
        source_message_id="message-1",
        scheduler_job_id="job-1",
        last_error=None,
        created_at=now,
        updated_at=now,
    )

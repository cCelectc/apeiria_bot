from __future__ import annotations

import asyncio
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


ESSENTIAL_TOOL_NAMES = (
    "future_task.cancel",
    "future_task.create",
    "future_task.list",
    "knowledge.search",
    "memory.search",
    "memory.write",
)
HTTP_OK = 200
KNOWLEDGE_CANDIDATE_COUNT = 20
KNOWLEDGE_EXCERPT_LIMIT = 320
KNOWLEDGE_RESULT_LIMIT = 5
TOOL_GUIDANCE_LIMIT = 900


def test_builtin_catalog_loads_idempotently_and_deterministically() -> None:
    from apeiria.ai.tools.catalog import load_builtin_tool_catalog
    from apeiria.ai.tools.registry import AIToolRegistry

    registry = AIToolRegistry()

    assert load_builtin_tool_catalog(registry) == len(ESSENTIAL_TOOL_NAMES)
    assert load_builtin_tool_catalog(registry) == 0
    assert (
        tuple(tool.name for tool in registry.snapshot().tools) == ESSENTIAL_TOOL_NAMES
    )

    tools = registry.snapshot().by_name
    assert tools["memory.search"].required_level is AIToolLevel.READ
    assert tools["memory.write"].required_level is AIToolLevel.WRITE
    assert tools["knowledge.search"].required_level is AIToolLevel.READ
    assert tools["future_task.create"].required_level is AIToolLevel.WRITE
    assert tools["future_task.list"].required_level is AIToolLevel.READ
    assert tools["future_task.cancel"].required_level is AIToolLevel.WRITE
    assert all(tool.origin == "builtin" for tool in tools.values())
    assert all(tool.manageable is False for tool in tools.values())
    assert all("essential" in tool.tags for tool in tools.values())


def test_builtin_catalog_excludes_host_level_tools() -> None:
    from apeiria.ai.tools.catalog import load_builtin_tool_catalog
    from apeiria.ai.tools.registry import AIToolRegistry

    registry = AIToolRegistry()
    load_builtin_tool_catalog(registry)

    forbidden_fragments = (
        "shell",
        "python",
        "browser",
        "file",
        "filesystem",
        "computer",
    )
    for tool in registry.snapshot().tools:
        searchable = f"{tool.name} {' '.join(tool.tags)} {tool.description}".lower()
        assert tool.required_level not in {AIToolLevel.HOST, AIToolLevel.ADMIN}
        assert not any(fragment in searchable for fragment in forbidden_fragments)


def test_lifecycle_loads_builtin_catalog_before_plugin_contributions() -> None:
    from apeiria.ai.contributions import AIPluginContributionRegistry
    from apeiria.app.ai.lifecycle import AIPluginLifecycleCoordinator

    order: list[str] = []
    tool_service = _FakeToolService(order)
    skill_service = _FakeSkillService(order, tool_service)
    future_service = _FakeFutureTaskService(order)
    contributions = AIPluginContributionRegistry()

    contributions.register_tool(tool=_plugin_tool("plugin.echo"))

    coordinator = AIPluginLifecycleCoordinator(
        contribution_registry=contributions,
        tool_service=tool_service,
        skill_service=skill_service,
        future_task_service=future_service,
        app_tool_loader=lambda: order.append("app_loader"),
    )

    asyncio.run(coordinator.startup())
    asyncio.run(coordinator.startup())

    assert order[: len(ESSENTIAL_TOOL_NAMES) + 4] == [
        "app_loader",
        *[f"tool:{name}" for name in ESSENTIAL_TOOL_NAMES],
        "builtin_catalog",
        "pending_tools",
        "tool:plugin.echo",
    ]
    assert skill_service.visible_tool_names[0] == (
        *ESSENTIAL_TOOL_NAMES,
        "plugin.echo",
    )
    assert future_service.calls == 1


def test_plugin_duplicate_with_builtin_catalog_is_rejected() -> None:
    from apeiria.ai.contributions import AIPluginContributionRegistry
    from apeiria.app.ai.lifecycle import AIPluginLifecycleCoordinator

    contributions = AIPluginContributionRegistry()
    contributions.register_tool(tool=_plugin_tool("memory.search"))
    tool_service = _FakeToolService([])
    coordinator = AIPluginLifecycleCoordinator(
        contribution_registry=contributions,
        tool_service=tool_service,
        skill_service=_FakeSkillService([], tool_service),
        future_task_service=_FakeFutureTaskService([]),
        app_tool_loader=lambda: None,
    )

    snapshot = coordinator.ensure_runtime_support_initialized()

    assert snapshot.initialized is False
    assert snapshot.initialization_source == "failed"
    assert "AIDuplicateToolError" in snapshot.diagnostics[0]


def test_memory_search_facade_delegates_with_actor_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apeiria.ai.memory.models import AIMemoryQuery
    from apeiria.ai.tools import essential as essential_tools

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

    monkeypatch.setattr(essential_tools, "ai_memory_service", FakeMemoryService())

    result = asyncio.run(
        essential_tools.search_memory(
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
    from apeiria.ai.tools import essential as essential_tools

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

    monkeypatch.setattr(essential_tools, "ai_memory_service", FakeMemoryService())

    result = asyncio.run(
        essential_tools.write_memory(
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
    from apeiria.ai.tools import essential as essential_tools

    calls: list[tuple[str, int, bool]] = []

    class FakeKnowledgeService:
        async def retrieve(
            self,
            *,
            query_text: str,
            limit: int,
            mutate_embeddings: bool = False,
            candidate_limit: int | None = None,
        ):
            del candidate_limit
            calls.append((query_text, limit, mutate_embeddings))
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
        essential_tools,
        "knowledge_retrieval_service",
        FakeKnowledgeService(),
    )

    result = asyncio.run(
        essential_tools.search_knowledge(
            "Apeiria knowledge",
            limit=99,
            context=_tool_context(),
        )
    )

    assert calls == [("Apeiria knowledge", KNOWLEDGE_RESULT_LIMIT, False)]
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
    from apeiria.ai.tools import essential as essential_tools
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
        essential_tools,
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
        essential_tools.create_future_task(
            description="Follow up",
            trigger_at="2026-05-15T09:00:00+08:00",
            context=context,
        )
    )
    list_result = asyncio.run(essential_tools.list_future_tasks(context=context))
    cancel_result = asyncio.run(
        essential_tools.cancel_future_task("task-1", context=context)
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
            origin="builtin",
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


def test_tool_diagnostics_route_reports_builtin_status(
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
    assert payload["memory.search"]["origin"] == "builtin"
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
        self.pending_tools: list[AIToolDefinition] = []

    def register(self, tool: AIToolDefinition) -> None:
        from apeiria.ai.tools.registry import AIDuplicateToolError

        if tool.name in self.tools and self.tools[tool.name] is not tool:
            raise AIDuplicateToolError(tool.name)
        if tool.name not in self.tools:
            self._order.append(f"tool:{tool.name}")
            self.tools[tool.name] = tool

    def load_builtin_catalog(self) -> int:
        from apeiria.ai.tools.catalog import load_builtin_tool_catalog

        count = load_builtin_tool_catalog(self)
        self._order.append("builtin_catalog")
        return count

    def list_tools(self) -> list[AIToolDefinition]:
        return [self.tools[name] for name in sorted(self.tools)]

    def register_pending_tools(self) -> int:
        self._order.append("pending_tools")
        count = 0
        for tool in self.pending_tools:
            if tool.name not in self.tools:
                self.tools[tool.name] = tool
                count += 1
        self.pending_tools = []
        return count


class _FakeToolService:
    def __init__(self, order: list[str]) -> None:
        self.registry = _FakeToolRegistry(order)


class _FakeSkillService:
    def __init__(self, order: list[str], tool_service: _FakeToolService) -> None:
        self._order = order
        self._tool_service = tool_service
        self.visible_tool_names: list[tuple[str, ...]] = []

    def ensure_initialized(
        self,
        *,
        skill_sources: tuple[Path, ...] = (),
    ) -> None:
        del skill_sources
        self._order.append("skills")
        self.visible_tool_names.append(
            tuple(tool.name for tool in self._tool_service.registry.list_tools())
        )

    def list_skills(self) -> list[object]:
        return []


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
        is_ignored=False,
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

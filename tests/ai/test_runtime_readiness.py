from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from apeiria.ai.config import AIPluginConfig
from apeiria.ai.model import AIModelBindingTarget, AIModelRouteQuery
from apeiria.ai.service import AIRuntimeDependencyStatus, AIService
from apeiria.ai.tools import AIToolPolicy, ToolGatewayResult
from apeiria.app.ai.reply_strategy import ReplyStrategyDecision
from apeiria.app.ai.runtime.session.context import (
    RuntimeContextMaterials,
    RuntimeTurnInput,
    RuntimeTurnSource,
)
from apeiria.app.ai.runtime.stages import RuntimePlanningInput
from apeiria.conversation.models import ChatSessionIdentity


class _ModelGatewayStub:
    def __init__(self, selected: Any) -> None:
        self.selected = selected
        self.calls: list[object] = []

    async def select_model(
        self,
        *,
        query: AIModelRouteQuery | None = None,
        target: AIModelBindingTarget | None = None,
    ) -> Any:
        self.calls.append(query)
        assert target is None
        return self.selected


class _RuntimeReadinessProbeStub:
    def __init__(
        self,
        components: tuple[AIRuntimeDependencyStatus, ...],
    ) -> None:
        self.components = components
        self.calls = 0

    def inspect(self) -> tuple[AIRuntimeDependencyStatus, ...]:
        self.calls += 1
        return self.components


def _ready_components() -> tuple[AIRuntimeDependencyStatus, ...]:
    return (
        AIRuntimeDependencyStatus(
            key="future_task_storage",
            available=True,
            detail="available",
        ),
        AIRuntimeDependencyStatus(
            key="delivery_attempt_storage",
            available=True,
            detail="available",
        ),
        AIRuntimeDependencyStatus(
            key="scheduler_recovery",
            available=True,
            detail="registered",
        ),
        AIRuntimeDependencyStatus(
            key="tool_registry",
            available=True,
            detail="3_tools",
        ),
        AIRuntimeDependencyStatus(
            key="skill_catalog",
            available=True,
            detail="initialized",
        ),
        AIRuntimeDependencyStatus(
            key="capability_bridge",
            available=True,
            detail="2_capabilities",
        ),
        AIRuntimeDependencyStatus(
            key="delivery_gateway",
            available=True,
            detail="onebot",
        ),
        AIRuntimeDependencyStatus(
            key="trace_storage",
            available=True,
            detail="available",
        ),
    )


def _components_with(
    degraded: AIRuntimeDependencyStatus,
) -> tuple[AIRuntimeDependencyStatus, ...]:
    return tuple(
        degraded if component.key == degraded.key else component
        for component in _ready_components()
    )


def _selected_model() -> SimpleNamespace:
    return SimpleNamespace(
        source=SimpleNamespace(source_id="source-main"),
        profile=SimpleNamespace(profile_id="reply-default", model_id="model-main"),
        resolved_model_name="gpt-main",
    )


def test_ai_service_status_reports_ready_reply_runtime() -> None:
    probe = _RuntimeReadinessProbeStub(_ready_components())
    service = AIService(
        model_gateway=_ModelGatewayStub(_selected_model()),
        runtime_readiness_probe=probe,
    )

    status = asyncio.run(service.get_status())

    assert status.phase == "runtime_ready"
    assert status.ready is True
    assert "reply generation has a selectable model" in status.summary
    assert "source-main:gpt-main" in status.summary
    assert "future-task storage available" in status.summary
    assert "delivery attempt storage available" in status.summary
    assert "scheduler recovery registered" in status.summary
    assert "tool registry available" in status.summary
    assert "skill catalog available" in status.summary
    assert "capability bridge available" in status.summary
    assert "delivery gateway available" in status.summary
    assert "trace storage available" in status.summary
    assert probe.calls == 1


def test_ai_service_status_reports_degraded_without_reply_model() -> None:
    gateway = _ModelGatewayStub(None)
    service = AIService(
        model_gateway=gateway,
        runtime_readiness_probe=_RuntimeReadinessProbeStub(_ready_components()),
    )

    status = asyncio.run(service.get_status())

    assert status.phase == "runtime_degraded"
    assert status.ready is False
    assert "Configure or enable a chat model" in status.summary
    assert len(gateway.calls) == 1


@pytest.mark.parametrize(
    ("degraded", "expected_summary"),
    [
        (
            AIRuntimeDependencyStatus(
                key="future_task_storage",
                available=False,
                detail="unavailable",
                next_step="Run `apeiria check` to initialize runtime storage.",
            ),
            "future-task storage unavailable",
        ),
        (
            AIRuntimeDependencyStatus(
                key="delivery_attempt_storage",
                available=False,
                detail="unavailable",
                next_step="Run `apeiria check` to initialize delivery attempts.",
            ),
            "delivery attempt storage unavailable",
        ),
        (
            AIRuntimeDependencyStatus(
                key="delivery_gateway",
                available=False,
                detail="adapter_unavailable",
                next_step="Enable a proactive delivery adapter.",
            ),
            "delivery gateway unavailable",
        ),
        (
            AIRuntimeDependencyStatus(
                key="trace_storage",
                available=False,
                detail="unavailable",
                next_step="Run `apeiria check` to repair trace storage.",
            ),
            "trace storage unavailable",
        ),
        (
            AIRuntimeDependencyStatus(
                key="scheduler_recovery",
                available=False,
                detail="not_registered",
                next_step="Load the AI plugin startup recovery hook.",
            ),
            "scheduler recovery not_registered",
        ),
        (
            AIRuntimeDependencyStatus(
                key="tool_registry",
                available=False,
                detail="not_initialized",
                next_step="Load the AI plugin startup lifecycle hook.",
            ),
            "tool registry not_initialized",
        ),
        (
            AIRuntimeDependencyStatus(
                key="skill_catalog",
                available=False,
                detail="not_initialized",
                next_step="Load the AI plugin startup lifecycle hook.",
            ),
            "skill catalog not_initialized",
        ),
        (
            AIRuntimeDependencyStatus(
                key="capability_bridge",
                available=False,
                detail="not_initialized",
                next_step="Load the AI plugin startup lifecycle hook.",
            ),
            "capability bridge not_initialized",
        ),
    ],
)
def test_ai_service_status_reports_degraded_runtime_dependency(
    degraded: AIRuntimeDependencyStatus,
    expected_summary: str,
) -> None:
    service = AIService(
        model_gateway=_ModelGatewayStub(_selected_model()),
        runtime_readiness_probe=_RuntimeReadinessProbeStub(_components_with(degraded)),
    )

    status = asyncio.run(service.get_status())

    assert status.phase == "runtime_degraded"
    assert status.ready is False
    assert expected_summary in status.summary
    assert status.next_step == degraded.next_step


def test_ai_service_status_does_not_initialize_missing_runtime_storage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    service = AIService(model_gateway=_ModelGatewayStub(_selected_model()))

    status = asyncio.run(service.get_status())

    assert status.phase == "runtime_degraded"
    assert "future-task storage unavailable" in status.summary
    assert not database_runtime.database_path().exists()


def test_runtime_readiness_inspects_failure_operation_storage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    from apeiria.app.ai.diagnostics.readiness import AIRuntimeReadinessProbe
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    statuses = {item.key: item for item in AIRuntimeReadinessProbe().inspect()}

    assert statuses["delivery_attempt_storage"].available is True
    assert statuses["trace_storage"].available is True


def test_runtime_readiness_reports_degraded_delivery_attempt_storage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    import sqlite3

    from apeiria.app.ai.diagnostics.readiness import AIRuntimeReadinessProbe
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_parent_dir()
    with sqlite3.connect(database_runtime.database_path()) as connection:
        connection.execute(
            """
            CREATE TABLE apeiria_schema_meta (
                id INTEGER PRIMARY KEY,
                schema_line TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO apeiria_schema_meta
            VALUES (1, 'apeiria_v1', 1, '2026-05-01T00:00:00+00:00',
                '2026-05-01T00:00:00+00:00')
            """
        )

    statuses = {item.key: item for item in AIRuntimeReadinessProbe().inspect()}

    assert statuses["delivery_attempt_storage"].available is False
    assert statuses["delivery_attempt_storage"].next_step == (
        "Run `apeiria check` to initialize delivery attempts."
    )


def test_reply_preparation_records_no_model_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apeiria.app.ai.runtime.planning import turn as planning_module

    identity = ChatSessionIdentity(
        session_id="scene-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id=None,
    )
    turn = RuntimeTurnInput(
        identity=identity,
        sender_id="user-1",
        source=RuntimeTurnSource(
            runtime_mode="message",
            message_text="hello",
            source_message_id="message-1",
            user_id="user-1",
            is_private=True,
        ),
    )
    context = RuntimeContextMaterials(
        turns=[],
        conversation_summary=None,
        relationship_target=object(),  # type: ignore[arg-type]
        model_target=AIModelBindingTarget(
            conversation_id="scene-1",
            group_id=None,
            user_id="user-1",
        ),
        tool_policy=AIToolPolicy(),
        persona=None,
        recalled_memories=[],
        relationship_context=None,
        person_profile=(),
        allowed_tools=(),
        initiative_bias=0.0,
    )
    social_decision = ReplyStrategyDecision(
        action="reply",
        should_speak=True,
        tool_mode="allow",
        reason_codes=(),
        reason_text="test",
        evidence={},
        decision_source="fallback",
    )
    diagnostics: list[str] = []

    async def prepare_tools(_request: object) -> ToolGatewayResult:
        return ToolGatewayResult(policy_text="", result_lines=(), turns=())

    async def select_model(*, task_class: str, target: object) -> None:
        del task_class, target

    def record_debug(message: str, *args: object) -> None:
        diagnostics.append(message.format(*args) if args else message)

    monkeypatch.setattr(planning_module, "get_ai_plugin_config", AIPluginConfig)
    monkeypatch.setattr(planning_module.tool_gateway, "prepare", prepare_tools)
    monkeypatch.setattr(planning_module, "select_model", select_model)
    monkeypatch.setattr(planning_module.logger, "debug", record_debug)

    result = asyncio.run(
        planning_module.plan_runtime_turn(
            planning_input=RuntimePlanningInput(
                stage="planning",
                trace_id="trace-1",
                turn=turn,
                context=context,
                social_decision=social_decision,
                current_time=datetime(2026, 4, 27, tzinfo=timezone.utc),
            ),
        )
    )

    assert result is None
    assert diagnostics == [
        "AI trace trace-1 skipped reply: no model selected for reply_default "
        "in session scene-1"
    ]

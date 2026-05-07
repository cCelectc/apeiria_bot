from __future__ import annotations

import asyncio
import importlib
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest

RECENT_TARGET_LIMIT = 7
RECENT_SESSION_LIMIT = 5
SCENE_TURN_LIMIT = 6
PROMPT_PREVIEW_TURN_LIMIT = 9
OLD_APP_PACKAGE_REMAINS_IMPORTABLE_ERROR = (
    "old AI application package remains importable"
)


def test_import_apeiria_ai_does_not_eagerly_import_runtime_services() -> None:
    for module_name in (
        "apeiria.ai",
        "apeiria.conversation.service",
        "apeiria.ai.memory.service",
        "apeiria.ai.model.runtime.gateway",
        "apeiria.ai.person.service",
        "apeiria.ai.persona.service",
        "apeiria.ai.relationship.service",
        "apeiria.app.ai.reply_strategy.service",
        "apeiria.ai.retention",
        "apeiria.ai.skills.service",
        "apeiria.ai.tools.gateway",
        "apeiria.ai.tools.service",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.ai")

    assert module.__name__ == "apeiria.ai"
    assert module.__all__ == [
        "ai_memory_service",
        "ai_person_profile_service",
        "ai_persona_service",
        "ai_relationship_service",
        "ai_retention_service",
        "ai_skill_service",
        "ai_tool_service",
    ]

    for module_name in (
        "apeiria.conversation.service",
        "apeiria.ai.memory.service",
        "apeiria.ai.model.runtime.gateway",
        "apeiria.ai.person.service",
        "apeiria.ai.persona.service",
        "apeiria.ai.relationship.service",
        "apeiria.app.ai.reply_strategy.service",
        "apeiria.ai.retention",
        "apeiria.ai.skills.service",
        "apeiria.ai.tools.gateway",
        "apeiria.ai.tools.service",
    ):
        assert module_name not in sys.modules

    assert not hasattr(module, "ai_service")
    assert not hasattr(module, "AIService")
    assert not hasattr(module, "AIServiceStatus")


def test_apeiria_ai_no_longer_re_exports_conversation_core() -> None:
    module = importlib.import_module("apeiria.ai")

    assert not hasattr(module, "chat_session_service")
    assert not hasattr(module, "ai_future_task_service")
    assert not hasattr(module, "reply_strategy_service")


class _ModelSelectorStub:
    async def select_model(self, *, query: object, target: object | None) -> Any:
        del query, target
        return SimpleNamespace(
            source=SimpleNamespace(source_id="source-public-surface"),
            profile=SimpleNamespace(model_id="model-public-surface"),
            resolved_model_name="gpt-public-surface",
        )


class _RuntimeReadinessProbeStub:
    def __init__(self, module: Any) -> None:
        self._module = module

    def inspect(self) -> tuple[Any, ...]:
        return (
            self._module.AIRuntimeDependencyStatus(
                key="future_task_storage",
                available=True,
                detail="available",
            ),
            self._module.AIRuntimeDependencyStatus(
                key="delivery_attempt_storage",
                available=True,
                detail="available",
            ),
            self._module.AIRuntimeDependencyStatus(
                key="scheduler_recovery",
                available=True,
                detail="registered",
            ),
            self._module.AIRuntimeDependencyStatus(
                key="delivery_gateway",
                available=True,
                detail="onebot",
            ),
            self._module.AIRuntimeDependencyStatus(
                key="trace_storage",
                available=True,
                detail="available",
            ),
        )


def test_ai_diagnostics_status_reports_model_readiness() -> None:
    module = importlib.import_module("apeiria.app.ai.diagnostics.readiness")
    diagnostics_module = importlib.import_module("apeiria.app.ai.diagnostics")
    diagnostics = diagnostics_module.AIDiagnosticsEntry(
        model_selector=_ModelSelectorStub(),
        runtime_readiness_probe=_RuntimeReadinessProbeStub(module),
    )

    status = asyncio.run(diagnostics.get_runtime_status())

    assert status.phase == "runtime_ready"
    assert status.ready is True
    assert "source-public-surface:gpt-public-surface" in status.summary


def test_import_app_ai_runtime_exposes_public_surface() -> None:
    for module_name in (
        "apeiria.app.ai.runtime",
        "apeiria.app.ai.pipeline",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.app.ai.runtime")

    expected_exports = [
        "AIRuntimeEntry",
        "AcceptedTurn",
        "CommitResult",
        "LazyAIRuntimeEntry",
        "RuntimeInput",
        "RuntimeTraceContext",
        "RuntimeTraceRecordInput",
        "TurnContextMaterials",
        "TurnExecutionResult",
        "TurnPlan",
        "TurnTrace",
        "create_default_ai_runtime_entry",
    ]

    assert module.__name__ == "apeiria.app.ai.runtime"
    assert module.__all__ == expected_exports
    for name in expected_exports:
        assert hasattr(module, name)
    assert "AISessionTurnEngine" not in module.__all__
    assert "RuntimeTurnInput" not in module.__all__
    assert "RuntimeContextInputBundle" not in module.__all__
    assert "apeiria.app.ai.pipeline" not in sys.modules


def test_app_ai_runtime_root_keeps_compatibility_names_absent() -> None:
    module = importlib.import_module("apeiria.app.ai.runtime")
    retired_names = (
        "AIRuntimeService",
        "ai_runtime_service",
        "AIRuntimeReplyRequest",
        "ReplyInputs",
        "DefaultRuntimePolicyStage",
        "DefaultRuntimeObservationStage",
        "DefaultRuntimeContextStage",
        "DefaultRuntimePlanningStage",
        "DefaultRuntimeExecutionStage",
        "DefaultRuntimeCommitStage",
        "DefaultRuntimeTraceStage",
        "select_pipeline_model",
        "select_pipeline_fallback_models",
    )

    for name in retired_names:
        assert name not in module.__all__
        assert not hasattr(module, name)


def test_old_ai_application_packages_are_not_public_surfaces() -> None:
    for module_name in (
        "apeiria.app.ai.pipeline",
        "apeiria.app.ai.session_read",
        "apeiria.app.ai.session_runtime",
        "apeiria.app.ai.future_task",
        "apeiria.app.ai.admin",
    ):
        sys.modules.pop(module_name, None)

    for module_name in (
        "apeiria.app.ai.pipeline",
        "apeiria.app.ai.session_read",
        "apeiria.app.ai.session_runtime",
        "apeiria.app.ai.future_task",
        "apeiria.app.ai.admin",
    ):
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        raise AssertionError(OLD_APP_PACKAGE_REMAINS_IMPORTABLE_ERROR)


def test_import_app_ai_reply_strategy_exposes_public_surface() -> None:
    for module_name in (
        "apeiria.app.ai.reply_strategy",
        "apeiria.app.ai.reply_strategy.service",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.app.ai.reply_strategy")

    assert module.__name__ == "apeiria.app.ai.reply_strategy"
    assert "reply_strategy_service" in module.__all__
    assert "apeiria.app.ai.reply_strategy.service" not in sys.modules
    assert (
        module.reply_strategy_service
        is sys.modules["apeiria.app.ai.reply_strategy.service"].reply_strategy_service
    )


def test_import_apeiria_ai_sessions_exposes_public_surface() -> None:
    for module_name in (
        "apeiria.app.ai.sessions",
        "apeiria.app.ai.session_read",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.app.ai.sessions")

    assert module.__name__ == "apeiria.app.ai.sessions"
    assert module.__all__ == [
        "AISessionsEntry",
        "AISessionsService",
        "ai_sessions_service",
    ]


def test_import_webui_ai_routes_package_exposes_router() -> None:
    for module_name in (
        "apeiria.webui.routes.ai",
        "apeiria.webui.routes.ai.future_tasks",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.webui.routes.ai")

    assert module.__name__ == "apeiria.webui.routes.ai"
    assert module.__all__ == ["router"]


def test_session_routes_delegate_to_ai_application_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = importlib.import_module("apeiria.webui.routes.ai.sessions")

    expected_sessions = [SimpleNamespace(session_id="session-1")]
    expected_turns = [SimpleNamespace(message_id="msg-1")]
    expected_targets = [SimpleNamespace(anchor_id="scene-1")]
    expected_preview = SimpleNamespace(session_id="session-1")

    class _Service:
        async def list_recent_targets(self, *, limit: int):
            assert limit == RECENT_TARGET_LIMIT
            return expected_targets

        async def list_recent_sessions(self, *, limit: int):
            assert limit == RECENT_SESSION_LIMIT
            return expected_sessions

        async def list_scene_turns(self, *, scene_id: str, limit: int):
            assert scene_id == "scene-1"
            assert limit == SCENE_TURN_LIMIT
            return expected_turns

        async def build_scene_prompt_preview(self, *, scene_id: str, turn_limit: int):
            assert scene_id == "scene-1"
            assert turn_limit == PROMPT_PREVIEW_TURN_LIMIT
            return expected_preview

    monkeypatch.setattr(
        routes,
        "ai_application",
        SimpleNamespace(sessions=_Service()),
    )
    monkeypatch.setattr(
        routes,
        "to_ai_recent_target_item",
        lambda item: {"anchor_id": item.anchor_id},
    )
    monkeypatch.setattr(
        routes,
        "to_ai_session_item",
        lambda item: {"session_id": item.session_id},
    )
    monkeypatch.setattr(
        routes,
        "to_ai_chat_message_item",
        lambda item: {"message_id": item.message_id},
    )
    monkeypatch.setattr(
        routes,
        "to_ai_session_prompt_preview_item",
        lambda item: {"session_id": item.session_id},
    )

    assert asyncio.run(
        routes.list_ai_recent_targets(None, limit=RECENT_TARGET_LIMIT)
    ) == [{"anchor_id": "scene-1"}]
    assert asyncio.run(routes.list_ai_scenes(None, limit=RECENT_SESSION_LIMIT)) == [
        {"session_id": "session-1"}
    ]
    assert asyncio.run(
        routes.list_ai_scene_turns(
            None,
            scene_id="scene-1",
            limit=SCENE_TURN_LIMIT,
        )
    ) == [{"message_id": "msg-1"}]
    assert asyncio.run(
        routes.get_ai_scene_prompt_preview(
            None,
            scene_id="scene-1",
            turn_limit=PROMPT_PREVIEW_TURN_LIMIT,
        )
    ) == {"session_id": "session-1"}


def test_stable_ai_root_service_exports_stay_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sys.modules.pop("apeiria.ai.model", None)

    module = importlib.import_module("apeiria.ai.model")
    service_module = importlib.import_module("apeiria.ai.model.runtime.service")

    assert module.model_invoker is service_module.model_invoker

    live_replacement = object()
    monkeypatch.setattr(service_module, "model_invoker", live_replacement)

    assert module.model_invoker is live_replacement

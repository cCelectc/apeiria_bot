from __future__ import annotations

import asyncio
import builtins
import importlib
import sys
from types import SimpleNamespace
from typing import Any

import pytest

RECENT_TARGET_LIMIT = 7
RECENT_SESSION_LIMIT = 5
SCENE_TURN_LIMIT = 6
PROMPT_PREVIEW_TURN_LIMIT = 9


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
        "apeiria.ai.service",
        "apeiria.ai.skills.service",
        "apeiria.ai.tools.gateway",
        "apeiria.ai.tools.service",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.ai")

    assert module.__name__ == "apeiria.ai"
    assert module.__all__ == [
        "AIService",
        "AIServiceStatus",
        "ai_memory_service",
        "ai_person_profile_service",
        "ai_persona_service",
        "ai_relationship_service",
        "ai_retention_service",
        "ai_service",
        "ai_skill_service",
        "ai_tool_service",
        "model_gateway",
        "tool_gateway",
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
        "apeiria.ai.service",
        "apeiria.ai.skills.service",
        "apeiria.ai.tools.gateway",
        "apeiria.ai.tools.service",
    ):
        assert module_name not in sys.modules

    ai_service = module.ai_service

    assert ai_service is sys.modules["apeiria.ai.service"].ai_service


def test_apeiria_ai_no_longer_re_exports_conversation_core() -> None:
    module = importlib.import_module("apeiria.ai")

    assert not hasattr(module, "chat_session_service")
    assert not hasattr(module, "ai_future_task_service")
    assert not hasattr(module, "reply_strategy_service")


class _ModelGatewayStub:
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


def test_ai_service_status_reports_model_readiness() -> None:
    module = importlib.import_module("apeiria.ai.service")
    service = module.AIService(
        model_gateway=_ModelGatewayStub(),
        runtime_readiness_probe=_RuntimeReadinessProbeStub(module),
    )

    status = asyncio.run(service.get_status())

    assert status.phase == "runtime_ready"
    assert status.ready is True
    assert "source-public-surface:gpt-public-surface" in status.summary


@pytest.mark.parametrize(
    "module_name",
    [
        "apeiria.ai.conversation",
        "apeiria.ai.conversation.identity",
        "apeiria.ai.conversation.models",
        "apeiria.ai.conversation.service",
    ],
)
def test_legacy_ai_conversation_core_modules_are_removed(module_name: str) -> None:
    sys.modules.pop(module_name, None)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


def test_import_app_ai_pipeline_exposes_public_surface() -> None:
    for module_name in (
        "apeiria.app.ai.pipeline",
        "apeiria.app.ai.pipeline.service",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.app.ai.pipeline")

    assert module.__name__ == "apeiria.app.ai.pipeline"
    assert module.__all__ == [
        "AIRuntimeComposeInput",
        "AIRuntimeService",
        "AITraceContext",
        "ai_runtime_service",
        "build_relationship_target",
        "load_relationship_context",
        "recall_memories",
        "store_extracted_memories",
        "update_relationship_state",
    ]
    assert "apeiria.app.ai.pipeline.service" not in sys.modules
    assert (
        module.ai_runtime_service
        is sys.modules["apeiria.app.ai.pipeline.service"].ai_runtime_service
    )


@pytest.mark.parametrize(
    "module_name",
    [
        "apeiria.ai.pipeline",
        "apeiria.ai.pipeline.composer",
        "apeiria.ai.pipeline.service",
        "apeiria.ai.reply_strategy",
        "apeiria.ai.reply_strategy.models",
        "apeiria.ai.reply_strategy.service",
        "apeiria.ai.reply_strategy.social_judgment",
        "apeiria.ai.session_read",
        "apeiria.ai.session_read.facade",
        "apeiria.ai.session_read.targets",
        "apeiria.ai.admin",
        "apeiria.ai.admin.control_service",
        "apeiria.ai.admin.runtime_service",
        "apeiria.ai.admin.service",
        "apeiria.ai.admin.sessions",
        "apeiria.ai.admin.types",
        "apeiria.ai.webui",
        "apeiria.ai.webui.routes",
        "apeiria.ai.webui.routes.sessions",
    ],
)
def test_legacy_ai_surface_modules_are_removed(module_name: str) -> None:
    sys.modules.pop(module_name, None)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


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


def test_import_apeiria_ai_session_read_exposes_public_surface() -> None:
    for module_name in (
        "apeiria.app.ai.session_read",
        "apeiria.app.ai.session_read.facade",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.app.ai.session_read")

    assert module.__name__ == "apeiria.app.ai.session_read"
    assert module.__all__ == [
        "AIRecentTarget",
        "AISessionPromptChannels",
        "AISessionPromptPreview",
        "AISessionPromptSection",
        "AISessionReadService",
        "ai_session_read_service",
    ]


def test_ai_runtime_admin_service_no_longer_owns_session_reads() -> None:
    module = importlib.import_module("apeiria.app.ai.admin.runtime_service")

    assert not hasattr(module.ai_runtime_admin_service, "list_recent_targets")
    assert not hasattr(module.ai_runtime_admin_service, "list_recent_sessions")
    assert not hasattr(module.ai_runtime_admin_service, "list_scene_turns")
    assert not hasattr(module.ai_runtime_admin_service, "build_scene_prompt_preview")


def test_import_ai_control_admin_service_is_safe_without_nonebot_plugin_orm() -> None:
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globalns: dict[str, object] | None = None,
        localns: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "nonebot_plugin_orm":
            raise AssertionError(name)
        return original_import(name, globalns, localns, fromlist, level)

    sys.modules.pop("apeiria.app.ai.admin.control_service", None)
    builtins.__import__ = guarded_import
    try:
        module = importlib.import_module("apeiria.app.ai.admin.control_service")
    finally:
        builtins.__import__ = original_import

    assert module.__name__ == "apeiria.app.ai.admin.control_service"


def test_app_ai_admin_package_no_longer_re_exports_legacy_service() -> None:
    module = importlib.import_module("apeiria.app.ai.admin")

    assert not hasattr(module, "AIAdminService")
    assert not hasattr(module, "ai_admin_service")


def test_import_webui_ai_routes_package_exposes_router() -> None:
    for module_name in (
        "apeiria.webui.routes.ai",
        "apeiria.webui.routes.ai.future_tasks",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.webui.routes.ai")

    assert module.__name__ == "apeiria.webui.routes.ai"
    assert module.__all__ == ["router"]


def test_import_session_read_targets_stays_lightweight() -> None:
    for module_name in (
        "apeiria.app.ai.session_read.targets",
        "apeiria.ai.model.runtime.service",
        "apeiria.ai.persona.service",
        "apeiria.app.ai.pipeline.composer",
        "apeiria.app.ai.reply_strategy.social_judgment",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.app.ai.session_read.targets")

    assert module.__name__ == "apeiria.app.ai.session_read.targets"
    assert "apeiria.ai.model.runtime.service" not in sys.modules
    assert "apeiria.ai.persona.service" not in sys.modules
    assert "apeiria.app.ai.pipeline.composer" not in sys.modules
    assert "apeiria.app.ai.reply_strategy.social_judgment" not in sys.modules


def test_session_routes_delegate_to_ai_session_read_service(
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

    monkeypatch.setattr(routes, "ai_session_read_service", _Service())
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


@pytest.mark.parametrize(
    ("package_name", "lazy_module_name", "symbol_name"),
    [
        ("apeiria.ai.memory", "apeiria.ai.memory.contracts", "AIMemoryCreateInput"),
        ("apeiria.ai.memory", "apeiria.ai.memory.contracts", "AIMemoryUpdateInput"),
        ("apeiria.ai.memory", "apeiria.ai.memory.service", "ai_memory_service"),
        ("apeiria.ai.model", "apeiria.ai.model.runtime.gateway", "model_gateway"),
        ("apeiria.ai.person", "apeiria.ai.person.service", "ai_person_profile_service"),
        ("apeiria.ai.persona", "apeiria.ai.persona.service", "ai_persona_service"),
        (
            "apeiria.ai.relationship",
            "apeiria.ai.relationship.service",
            "ai_relationship_service",
        ),
        (
            "apeiria.ai.relationship",
            "apeiria.ai.relationship.scoring",
            "project_emotion",
        ),
        ("apeiria.ai.skills", "apeiria.ai.skills.service", "ai_skill_service"),
        (
            "apeiria.ai.tools",
            "apeiria.ai.tools.contracts",
            "AIToolExecutionCreateInput",
        ),
        ("apeiria.ai.tools", "apeiria.ai.tools.gateway", "ToolGateway"),
        ("apeiria.ai.tools", "apeiria.ai.tools.gateway", "ToolGatewayRequest"),
        ("apeiria.ai.tools", "apeiria.ai.tools.gateway", "ToolGatewayResult"),
        ("apeiria.ai.tools", "apeiria.ai.tools.gateway", "ToolResult"),
        ("apeiria.ai.tools", "apeiria.ai.tools.gateway", "tool_gateway"),
        (
            "apeiria.ai.tools",
            "apeiria.ai.tools.policy",
            "ai_tool_policy_binding_service",
        ),
        ("apeiria.ai.tools", "apeiria.ai.tools.service", "ai_tool_service"),
    ],
)
def test_stable_ai_root_exports_stay_lazy(
    package_name: str,
    lazy_module_name: str,
    symbol_name: str,
) -> None:
    sys.modules.pop(package_name, None)
    sys.modules.pop(lazy_module_name, None)

    module = importlib.import_module(package_name)

    assert symbol_name in module.__all__
    assert lazy_module_name not in sys.modules

    value = getattr(module, symbol_name)

    assert value is getattr(sys.modules[lazy_module_name], symbol_name)


def test_stable_ai_root_service_exports_stay_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sys.modules.pop("apeiria.ai.model", None)

    module = importlib.import_module("apeiria.ai.model")
    service_module = importlib.import_module("apeiria.ai.model.runtime.service")

    assert module.ai_model_facade is service_module.ai_model_facade

    live_replacement = object()
    monkeypatch.setattr(service_module, "ai_model_facade", live_replacement)

    assert module.ai_model_facade is live_replacement

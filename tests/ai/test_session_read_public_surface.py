from __future__ import annotations

import asyncio
import importlib
import sys
from types import SimpleNamespace

import pytest

RECENT_TARGET_LIMIT = 7
RECENT_SESSION_LIMIT = 5
SCENE_TURN_LIMIT = 6
PROMPT_PREVIEW_TURN_LIMIT = 9


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
        "AISessionReadService",
        "ai_session_read_service",
    ]


def test_legacy_ai_session_read_package_is_gone() -> None:
    for module_name in (
        "apeiria.ai.session_read",
        "apeiria.ai.session_read.facade",
        "apeiria.ai.session_read.targets",
    ):
        sys.modules.pop(module_name, None)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("apeiria.ai.session_read")


def test_ai_runtime_admin_service_no_longer_owns_session_reads() -> None:
    module = importlib.import_module("apeiria.ai.admin.runtime_service")

    assert not hasattr(module.ai_runtime_admin_service, "list_recent_targets")
    assert not hasattr(module.ai_runtime_admin_service, "list_recent_sessions")
    assert not hasattr(module.ai_runtime_admin_service, "list_scene_turns")
    assert not hasattr(module.ai_runtime_admin_service, "build_scene_prompt_preview")


def test_legacy_ai_admin_sessions_module_is_gone() -> None:
    sys.modules.pop("apeiria.ai.admin.sessions", None)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("apeiria.ai.admin.sessions")


def test_legacy_ai_admin_types_module_is_gone() -> None:
    sys.modules.pop("apeiria.ai.admin.types", None)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("apeiria.ai.admin.types")


def test_import_session_read_targets_stays_lightweight() -> None:
    for module_name in (
        "apeiria.app.ai.session_read.targets",
        "apeiria.ai.model.service",
        "apeiria.ai.persona.service",
        "apeiria.ai.pipeline.composer",
        "apeiria.ai.reply_strategy.social_judgment",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.app.ai.session_read.targets")

    assert module.__name__ == "apeiria.app.ai.session_read.targets"
    assert "apeiria.ai.model.service" not in sys.modules
    assert "apeiria.ai.persona.service" not in sys.modules
    assert "apeiria.ai.pipeline.composer" not in sys.modules
    assert "apeiria.ai.reply_strategy.social_judgment" not in sys.modules


def test_session_routes_delegate_to_ai_session_read_service(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    routes = importlib.import_module("apeiria.ai.webui.routes.sessions")

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

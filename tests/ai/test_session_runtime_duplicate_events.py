from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest  # noqa: TC002

from apeiria.ai.config import AIPluginConfig
from apeiria.ai.tools import AIToolPolicy
from apeiria.app.ai.pipeline import service as service_module
from apeiria.app.ai.pipeline.service import AIRuntimeService
from apeiria.app.ai.reply_strategy import ReplyStrategyDecision, WakeContext
from apeiria.conversation.models import ChatSessionIdentity
from tests.ai.agent_turn_helpers import selected_model


class _FakeChatSessionService:
    def __init__(self) -> None:
        self.calls = 0
        self.identity = ChatSessionIdentity(
            session_id="session-1",
            platform="test",
            bot_id="bot-1",
            scene_type="group",
            scene_id="scene-1",
            subject_id="user-1",
        )

    async def ingest_event(self, *_args: Any, **_kwargs: Any) -> object:
        self.calls += 1
        return self.identity, SimpleNamespace(
            message_id=f"local-msg-{self.calls}",
            platform_message_id="platform-msg-1",
        )


async def _noop_observation_effects(*_args: Any, **_kwargs: Any) -> None:
    return None


def test_duplicate_platform_event_stops_before_ai_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counts = {
        "memory": 0,
        "inputs": 0,
        "social": 0,
        "model": 0,
        "assistant": 0,
    }
    service = AIRuntimeService()
    chat_service = _FakeChatSessionService()

    monkeypatch.setattr(service_module, "ensure_app_ai_tools_loaded", lambda: None)
    monkeypatch.setattr(
        service_module,
        "ai_skill_service",
        SimpleNamespace(ensure_initialized=lambda: None),
    )
    monkeypatch.setattr(service_module, "get_ai_plugin_config", AIPluginConfig)
    monkeypatch.setattr(
        service_module,
        "build_wake_context",
        lambda *_args, **_kwargs: WakeContext(
            bot_self_id="bot-1",
            user_id="user-1",
            message_text="hello",
            is_tome=True,
            is_private=False,
            is_future_task=False,
            allow_group_initiative=True,
        ),
    )
    monkeypatch.setattr(
        service_module,
        "evaluate_wake",
        lambda _wake_context: SimpleNamespace(should_process=True),
    )
    monkeypatch.setattr(
        service_module,
        "ai_retention_service",
        SimpleNamespace(maybe_schedule_cleanup=lambda **_kwargs: None),
    )
    monkeypatch.setattr(service_module, "chat_session_service", chat_service)
    monkeypatch.setattr(
        service_module,
        "reply_strategy_service",
        SimpleNamespace(notify_replied=lambda _session_id: None),
    )

    async def store_extracted_memories(*_args: Any, **_kwargs: Any) -> object:
        counts["memory"] += 1
        return SimpleNamespace(sentiment=object())

    async def gather_reply_inputs(*_args: Any, **_kwargs: Any) -> object:
        counts["inputs"] += 1
        return SimpleNamespace(
            turns=[],
            conversation_summary=None,
            relationship_context=None,
            persona=None,
            allowed_tools=(),
            initiative_bias=0.0,
            model_target=object(),
            tool_policy=AIToolPolicy(),
            recalled_memories=[],
            person_profile=(),
        )

    async def decide_whether_to_speak(
        *_args: Any,
        **_kwargs: Any,
    ) -> ReplyStrategyDecision:
        counts["social"] += 1
        return ReplyStrategyDecision(
            action="reply",
            should_speak=True,
            tool_mode="avoid",
            reason_codes=("direct",),
            reason_text="direct",
            evidence={},
            decision_source="llm",
        )

    async def prepare_generation(*_args: Any, **_kwargs: Any) -> object:
        return SimpleNamespace(
            skill_runtime=SimpleNamespace(
                policy_text="No tools.",
                result_lines=(),
                turns=(),
                available_tools=(),
            ),
            selected=selected_model("duplicate"),
            skill_activation=None,
            pre_tool_task_class="reply_default",
        )

    async def generate_reply(*_args: Any, **_kwargs: Any) -> object:
        counts["model"] += 1
        return SimpleNamespace(
            response=SimpleNamespace(
                content="reply",
                source_id="source-1",
                model_name="model-1",
            ),
            delivery_result=None,
            skill_runtime=SimpleNamespace(turns=[]),
            post_tool_task_class=None,
            turn_result=None,
        )

    class ReplyPersistenceStage:
        async def persist_tool_observations(self, **_: object) -> str:
            return "not_required"

        async def persist_assistant_message(self, **_: object) -> None:
            counts["assistant"] += 1

        async def rebuild_context_window(self, **_: object) -> None:
            return None

    monkeypatch.setattr(
        service_module,
        "store_extracted_memories",
        store_extracted_memories,
    )
    monkeypatch.setattr(
        service_module,
        "apply_reply_observation_effects",
        _noop_observation_effects,
    )
    monkeypatch.setattr(service_module, "gather_reply_inputs", gather_reply_inputs)
    monkeypatch.setattr(
        service_module,
        "decide_whether_to_speak",
        decide_whether_to_speak,
    )
    monkeypatch.setattr(service_module, "prepare_generation", prepare_generation)
    monkeypatch.setattr(service_module, "generate_reply", generate_reply)
    monkeypatch.setattr(
        service_module,
        "AssistantReplyPersistenceStage",
        ReplyPersistenceStage,
    )

    bot = SimpleNamespace(self_id="bot-1")
    event = SimpleNamespace(get_user_id=lambda: "user-1", is_tome=lambda: True)

    first = asyncio.run(service.handle_message(bot, event))  # type: ignore[arg-type]
    duplicate = asyncio.run(service.handle_message(bot, event))  # type: ignore[arg-type]

    assert first == "reply"
    assert duplicate is None
    expected_ingest_calls = 2
    assert chat_service.calls == expected_ingest_calls
    assert counts == {
        "memory": 1,
        "inputs": 1,
        "social": 1,
        "model": 1,
        "assistant": 1,
    }

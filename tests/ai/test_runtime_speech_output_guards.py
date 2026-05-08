from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from apeiria.app.ai.runtime.commit.delivery import (
    DeliveryGateway,
    DeliveryOutcome,
    DeliveryRequest,
    deliver_generated_reply,
)
from apeiria.app.ai.runtime.session.context import RuntimeTurnInput, RuntimeTurnSource
from apeiria.conversation.models import ChatSessionIdentity


def test_generated_delivery_request_is_text_only() -> None:
    request = DeliveryRequest(
        trace_id="trace-1",
        session_id="session-1",
        runtime_mode="future_task",
        bot_id="bot-1",
        platform="onebot",
        scene_type="private",
        scene_id="1001",
        message_text="hello",
    )

    assert request.message_text == "hello"
    assert not hasattr(request, "audio_bytes")
    assert not hasattr(request, "asset_id")
    assert not hasattr(request, "response_format")


def test_future_task_delivery_does_not_create_voice_asset(
    monkeypatch: Any,
) -> None:
    from apeiria.app.ai.runtime.commit import delivery as delivery_module

    adapter = _Adapter()
    monkeypatch.setattr(
        delivery_module,
        "delivery_gateway",
        DeliveryGateway(adapters=(adapter,)),
    )
    monkeypatch.setattr(
        delivery_module.delivery_attempt_repository,
        "get_delivered_attempt",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        delivery_module.delivery_attempt_repository,
        "create_or_reuse_pending",
        lambda _input: SimpleNamespace(attempt_id="attempt-1"),
    )
    monkeypatch.setattr(
        delivery_module.delivery_attempt_repository,
        "mark_delivered",
        lambda **_kwargs: None,
    )

    outcome = asyncio.run(
        deliver_generated_reply(
            _future_task_turn(),
            "assistant text",
            trace_id="trace-1",
        )
    )

    assert outcome is not None
    assert outcome.delivered is True
    assert adapter.requests[0].message_text == "assistant text"
    assert not hasattr(adapter.requests[0], "audio_bytes")


def _future_task_turn() -> RuntimeTurnInput:
    return RuntimeTurnInput(
        identity=ChatSessionIdentity(
            session_id="session-1",
            platform="onebot",
            bot_id="bot-1",
            scene_type="private",
            scene_id="1001",
            subject_id="1001",
        ),
        source=RuntimeTurnSource(
            runtime_mode="future_task",
            message_text="remind me",
            source_message_id="task-1",
            user_id="1001",
        ),
        sender_id="bot-1",
        future_task=SimpleNamespace(task_id="task-1"),
    )


class _Adapter:
    supports_partial_replies = False

    def __init__(self) -> None:
        self.requests: list[DeliveryRequest] = []

    def can_deliver(self, request: DeliveryRequest) -> bool:
        return request.platform == "onebot"

    async def deliver(self, request: DeliveryRequest) -> DeliveryOutcome:
        self.requests.append(request)
        return DeliveryOutcome(delivered=True, channel="onebot")

    async def deliver_partial_reply(self, request: object) -> DeliveryOutcome:
        del request
        return DeliveryOutcome(delivered=False)

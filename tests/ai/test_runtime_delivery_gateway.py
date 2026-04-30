from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest
from apeiria.conversation.models import ChatSessionIdentity


def _future_task_request() -> AIRuntimeReplyRequest:
    return AIRuntimeReplyRequest(
        identity=ChatSessionIdentity(
            session_id="session-1",
            platform="onebot",
            bot_id="bot-1",
            scene_type="group",
            scene_id="10001",
            subject_id=None,
        ),
        message_text="wake up",
        source_message_id="message-1",
        user_id="user-1",
        sender_id="bot-1",
        runtime_mode="future_task",
    )


def test_deliver_generated_reply_uses_delivery_gateway(monkeypatch: Any) -> None:
    from apeiria.app.ai.pipeline import delivery_steps

    captured: list[delivery_steps.DeliveryRequest] = []

    class FakeGateway:
        async def deliver(
            self,
            request: delivery_steps.DeliveryRequest,
        ) -> delivery_steps.DeliveryOutcome:
            captured.append(request)
            return delivery_steps.DeliveryOutcome(
                delivered=True,
                status="delivered",
                channel="onebot",
            )

    monkeypatch.setattr(delivery_steps, "delivery_gateway", FakeGateway())

    result = asyncio.run(
        delivery_steps.deliver_generated_reply(
            _future_task_request(),
            "hello",
            trace_id="trace-1",
        )
    )

    assert result is not None
    assert result.delivered is True
    assert captured == [
        delivery_steps.DeliveryRequest(
            trace_id="trace-1",
            session_id="session-1",
            runtime_mode="future_task",
            bot_id="bot-1",
            platform="onebot",
            scene_type="group",
            scene_id="10001",
            message_text="hello",
        )
    ]


def test_message_turn_does_not_invoke_proactive_delivery_gateway(
    monkeypatch: Any,
) -> None:
    from apeiria.app.ai.pipeline import delivery_steps

    class FakeGateway:
        async def deliver(self, request: object) -> None:
            raise AssertionError(request)

    request = _future_task_request()
    request = AIRuntimeReplyRequest(
        identity=request.identity,
        message_text=request.message_text,
        source_message_id=request.source_message_id,
        user_id=request.user_id,
        sender_id=request.sender_id,
        runtime_mode="message",
    )
    monkeypatch.setattr(delivery_steps, "delivery_gateway", FakeGateway())

    result = asyncio.run(
        delivery_steps.deliver_generated_reply(
            request,
            "hello",
            trace_id="trace-1",
        )
    )

    assert result is None


def test_onebot_delivery_adapter_owns_platform_api_conversion(
    monkeypatch: Any,
) -> None:
    import apeiria.app.ai.pipeline.delivery_steps as delivery_module
    from apeiria.app.ai.pipeline.delivery_steps import (
        DeliveryRequest,
        OneBotDeliveryAdapter,
    )

    calls: list[tuple[str, dict[str, object]]] = []

    class FakeBot:
        async def call_api(self, api_name: str, **kwargs: object) -> dict[str, int]:
            calls.append((api_name, kwargs))
            return {"message_id": 123}

    def get_bots() -> dict[str, FakeBot]:
        return {"bot-1": FakeBot()}

    monkeypatch.setattr(delivery_module, "_get_nonebot_bots", get_bots)

    result = asyncio.run(
        OneBotDeliveryAdapter().deliver(
            DeliveryRequest(
                trace_id="trace-1",
                session_id="session-1",
                runtime_mode="future_task",
                bot_id="bot-1",
                platform="onebot",
                scene_type="group",
                scene_id="10001",
                message_text="hello",
            )
        )
    )

    assert result.delivered is True
    assert result.remote_message_id == "123"
    assert calls == [("send_group_msg", {"group_id": 10001, "message": "hello"})]


def test_onebot_delivery_adapter_returns_bounded_failures(monkeypatch: Any) -> None:
    import apeiria.app.ai.pipeline.delivery_steps as delivery_module
    from apeiria.app.ai.pipeline.delivery_steps import (
        DeliveryRequest,
        OneBotDeliveryAdapter,
    )

    monkeypatch.setattr(delivery_module, "_get_nonebot_bots", dict)

    result = asyncio.run(
        OneBotDeliveryAdapter().deliver(
            DeliveryRequest(
                trace_id="trace-1",
                session_id="session-1",
                runtime_mode="future_task",
                bot_id="bot-1",
                platform="onebot",
                scene_type="private",
                scene_id="10001",
                message_text="hello",
            )
        )
    )

    assert result.delivered is False
    assert result.status == "failed"
    assert result.reason == "bot_not_connected"


def test_onebot_api_names_stay_out_of_runtime_stages() -> None:
    project_root = Path(__file__).resolve().parents[2]
    runtime_sources = [
        project_root / "apeiria" / "app" / "ai" / "pipeline" / "generation_steps.py",
        project_root / "apeiria" / "app" / "ai" / "pipeline" / "service.py",
        project_root / "apeiria" / "app" / "ai" / "session_runtime" / "engine.py",
    ]

    for source_path in runtime_sources:
        source = source_path.read_text(encoding="utf-8")
        assert "send_group_msg" not in source
        assert "send_private_msg" not in source

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import apeiria.app.ai.runtime.commit.delivery as delivery_steps
from apeiria.app.ai.runtime.live import AIRuntimeTurnRequest
from apeiria.conversation.models import ChatSessionIdentity

if TYPE_CHECKING:
    from pathlib import Path


def _future_task_request() -> AIRuntimeTurnRequest:
    return _runtime_request()


def _future_task_delivery_request() -> AIRuntimeTurnRequest:
    from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition

    now = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)
    return _runtime_request(
        future_task=AIFutureTaskDefinition(
            task_id="task-1",
            session_id="session-1",
            platform="onebot",
            scene_type="group",
            scene_id="10001",
            user_id="user-1",
            title="Wake",
            description="wake up",
            trigger_at=now,
            status="running",
            source_message_id="message-1",
            scheduler_job_id=None,
            last_error=None,
            created_at=now,
            updated_at=now,
        )
    )


def _runtime_request(
    *,
    future_task: object | None = None,
    runtime_mode: str = "future_task",
) -> AIRuntimeTurnRequest:
    return AIRuntimeTurnRequest(
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
        runtime_mode=runtime_mode,  # type: ignore[arg-type]
        future_task=future_task,  # type: ignore[arg-type]
    )


def test_deliver_generated_reply_uses_delivery_gateway(monkeypatch: Any) -> None:

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

    class FakeGateway:
        async def deliver(self, request: object) -> None:
            raise AssertionError(request)

    request = _runtime_request(runtime_mode="message")
    monkeypatch.setattr(delivery_steps, "delivery_gateway", FakeGateway())

    result = asyncio.run(
        delivery_steps.deliver_generated_reply(
            request,
            "hello",
            trace_id="trace-1",
        )
    )

    assert result is None


def test_future_task_delivery_records_delivered_attempt(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    from apeiria.app.ai.future_tasks.delivery_attempts import (
        delivery_attempt_repository,
    )
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
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
                remote_message_id="123",
            )

    monkeypatch.setattr(delivery_steps, "delivery_gateway", FakeGateway())

    result = asyncio.run(
        delivery_steps.deliver_generated_reply(
            _future_task_delivery_request(),
            "hello",
            trace_id="trace-1",
        )
    )
    attempt = delivery_attempt_repository.get_delivered_attempt(
        task_id="task-1",
        delivery_intent="future_task:task-1:reply",
    )

    assert result is not None
    assert result.delivered is True
    assert captured
    assert attempt is not None
    assert attempt.trace_id == "trace-1"
    assert attempt.status == "delivered"
    assert attempt.remote_message_id == "123"


def test_future_task_delivery_reuses_delivered_attempt_without_gateway(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    from apeiria.app.ai.future_tasks.delivery_attempts import (
        AIDeliveryAttemptCreateInput,
        delivery_attempt_repository,
    )
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    now = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)
    attempt = delivery_attempt_repository.create_or_reuse_pending(
        AIDeliveryAttemptCreateInput(
            task_id="task-1",
            trace_id="trace-old",
            session_id="session-1",
            delivery_intent="future_task:task-1:reply",
            platform="onebot",
            scene_type="group",
            scene_id="10001",
            message_preview="hello",
            message_hash="hash-old",
            created_at=now,
        )
    )
    delivery_attempt_repository.mark_delivered(
        attempt_id=attempt.attempt_id,
        channel="onebot",
        remote_message_id="123",
        delivered_at=now,
    )

    class FakeGateway:
        async def deliver(self, request: object) -> None:
            raise AssertionError(request)

    monkeypatch.setattr(delivery_steps, "delivery_gateway", FakeGateway())

    result = asyncio.run(
        delivery_steps.deliver_generated_reply(
            _future_task_delivery_request(),
            "hello again",
            trace_id="trace-new",
        )
    )

    assert result is not None
    assert result.delivered is True
    assert result.reason == "already_delivered"
    assert result.channel == "onebot"
    assert result.remote_message_id == "123"


def test_future_task_delivery_failure_is_retryable(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    captured: list[str] = []

    class FakeGateway:
        async def deliver(
            self,
            request: delivery_steps.DeliveryRequest,
        ) -> delivery_steps.DeliveryOutcome:
            captured.append(request.trace_id)
            if len(captured) == 1:
                return delivery_steps.DeliveryOutcome(
                    delivered=False,
                    reason="bot_not_connected",
                    channel="onebot",
                )
            return delivery_steps.DeliveryOutcome(
                delivered=True,
                channel="onebot",
                remote_message_id="456",
            )

    monkeypatch.setattr(delivery_steps, "delivery_gateway", FakeGateway())

    first = asyncio.run(
        delivery_steps.deliver_generated_reply(
            _future_task_delivery_request(),
            "hello",
            trace_id="trace-1",
        )
    )
    second = asyncio.run(
        delivery_steps.deliver_generated_reply(
            _future_task_delivery_request(),
            "hello",
            trace_id="trace-2",
        )
    )

    with database_runtime.connect_sync() as connection:
        rows = connection.execute(
            """
            SELECT status, attempt_count, reason, remote_message_id
            FROM ai_delivery_attempt
            ORDER BY id ASC
            """
        ).fetchall()

    assert first is not None
    assert first.delivered is False
    assert second is not None
    assert second.delivered is True
    assert captured == ["trace-1", "trace-2"]
    assert rows == [
        ("failed", 1, "bot_not_connected", None),
        ("delivered", 1, None, "456"),
    ]


def test_onebot_delivery_adapter_owns_platform_api_conversion(
    monkeypatch: Any,
) -> None:
    import apeiria.app.ai.runtime.commit.delivery as delivery_module
    from apeiria.app.ai.runtime.commit.delivery import (
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
    import apeiria.app.ai.runtime.commit.delivery as delivery_module
    from apeiria.app.ai.runtime.commit.delivery import (
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

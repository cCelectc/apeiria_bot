from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

_MAX_BOUNDED_DIAGNOSTIC_LENGTH = 220


def test_delivery_attempt_table_is_created(
    monkeypatch: Any,
    tmp_path: Any,
) -> None:
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    with database_runtime.connect_sync() as connection:
        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(ai_delivery_attempt)")
        }

    assert {
        "attempt_id",
        "task_id",
        "trace_id",
        "session_id",
        "delivery_intent",
        "status",
        "diagnostics_json",
        "remote_message_id",
        "attempt_count",
        "created_at",
        "updated_at",
    } <= columns


def test_delivery_attempt_repository_reuses_pending_and_marks_delivered(
    monkeypatch: Any,
    tmp_path: Any,
) -> None:
    repository = _delivery_attempt_repository()
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    now = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)

    attempts = repository.AIDeliveryAttemptRepository()
    created = attempts.create_or_reuse_pending(
        repository.AIDeliveryAttemptCreateInput(
            task_id="task-1",
            trace_id="trace-1",
            session_id="session-1",
            delivery_intent="future-task:task-1",
            platform="onebot",
            scene_type="group",
            scene_id="10001",
            message_preview="hello",
            message_hash="hash-1",
            created_at=now,
        )
    )
    reused = attempts.create_or_reuse_pending(
        repository.AIDeliveryAttemptCreateInput(
            task_id="task-1",
            trace_id="trace-1",
            session_id="session-1",
            delivery_intent="future-task:task-1",
            platform="onebot",
            scene_type="group",
            scene_id="10001",
            message_preview="hello again",
            message_hash="hash-2",
            created_at=now,
        )
    )

    delivered = attempts.mark_delivered(
        attempt_id=created.attempt_id,
        channel="onebot",
        remote_message_id="123",
        delivered_at=now,
    )
    loaded = attempts.get_delivered_attempt(
        task_id="task-1",
        delivery_intent="future-task:task-1",
    )

    assert reused == created
    assert delivered.status == "delivered"
    assert delivered.attempt_count == 1
    assert delivered.channel == "onebot"
    assert delivered.remote_message_id == "123"
    assert delivered.delivered_at == now
    assert loaded == delivered


def test_delivery_attempt_repository_records_failed_retryable_attempt(
    monkeypatch: Any,
    tmp_path: Any,
) -> None:
    repository = _delivery_attempt_repository()
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    now = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)

    attempts = repository.AIDeliveryAttemptRepository()
    created = attempts.create_or_reuse_pending(
        repository.AIDeliveryAttemptCreateInput(
            task_id="task-1",
            trace_id="trace-1",
            session_id="session-1",
            delivery_intent="future-task:task-1",
            platform="onebot",
            scene_type="private",
            scene_id="10001",
            message_preview="hello",
            message_hash="hash-1",
            created_at=now,
        )
    )

    failed = attempts.mark_failed(
        attempt_id=created.attempt_id,
        reason="adapter_error",
        diagnostics={"api_key": "secret-value", "error": "x" * 400},
        failed_at=now,
    )
    retry = attempts.create_or_reuse_pending(
        repository.AIDeliveryAttemptCreateInput(
            task_id="task-1",
            trace_id="trace-2",
            session_id="session-1",
            delivery_intent="future-task:task-1",
            platform="onebot",
            scene_type="private",
            scene_id="10001",
            message_preview="retry",
            message_hash="hash-2",
            created_at=now,
        )
    )

    assert failed.status == "failed"
    assert failed.attempt_count == 1
    assert failed.reason == "adapter_error"
    assert failed.diagnostics["api_key"] == "[redacted]"
    assert len(str(failed.diagnostics["error"])) <= _MAX_BOUNDED_DIAGNOSTIC_LENGTH
    assert retry.status == "pending"
    assert retry.attempt_id != created.attempt_id
    assert retry.trace_id == "trace-2"


def _delivery_attempt_repository() -> Any:
    try:
        from apeiria.app.ai.future_task import delivery_attempts
    except ModuleNotFoundError as exc:
        pytest.fail(f"missing delivery attempt repository module: {exc}")
    return delivery_attempts

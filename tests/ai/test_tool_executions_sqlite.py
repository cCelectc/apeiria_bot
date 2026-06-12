from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_tool_executions_use_sqlite_runtime(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    from apeiria.ai.tools.service import AIToolObservationCreateInput, AIToolService

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    _seed_chat_session("session-1")

    async def scenario() -> None:
        service = AIToolService()
        created = await service.record_observation(
            AIToolObservationCreateInput(
                session_id="session-1",
                tool_name="memory.search",
                status="success",
                trace_id="trace-1",
                input_payload={"query": "hello"},
                output_payload={"memory_ids": ["memory-1"]},
            ),
        )
        rows = await service.list_executions(session_id="session-1")

        assert rows == [created]
        assert rows[0].input_json is not None
        assert rows[0].output_json is not None

    asyncio.run(scenario())


def test_tool_execution_payloads_are_sanitized(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    from apeiria.ai.tools.service import AIToolObservationCreateInput, AIToolService

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    _seed_chat_session("session-1")

    async def scenario() -> None:
        service = AIToolService()
        await service.record_observation(
            AIToolObservationCreateInput(
                session_id="session-1",
                tool_name="memory.search",
                status="error",
                trace_id="trace-1",
                input_payload={"api_key": "sk-secret", "query": "hello"},
                output_payload={
                    "error": "Authorization: Bearer sk-secret",
                    "items": list(range(25)),
                    "long": "x" * 400,
                },
            ),
        )
        rows = await service.list_executions(session_id="session-1")

        assert rows[0].input_json is not None
        assert rows[0].output_json is not None
        input_payload = json.loads(rows[0].input_json)
        output_payload = json.loads(rows[0].output_json)
        assert input_payload["api_key"] == "[redacted]"
        assert output_payload["error"] == ("Authorization: Bearer [redacted]")
        assert output_payload["items"] == list(range(20))
        assert output_payload["long"] == "x" * 200

    asyncio.run(scenario())


def test_tool_execution_retention_deletes_old_sqlite_rows(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    from apeiria.ai.retention import AIRetentionService
    from apeiria.db.engine import close_engine, init_engine

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    _seed_chat_session("session-1")
    old_time = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(
        timespec="seconds"
    )
    new_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with database_runtime.connect_sync() as connection:
        connection.execute(
            """
            INSERT INTO ai_tool_execution (
                execution_id,
                session_id,
                tool_name,
                status,
                created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("tool_exec_old", "session-1", "memory.search", "success", old_time),
        )
        connection.execute(
            """
            INSERT INTO ai_tool_execution (
                execution_id,
                session_id,
                tool_name,
                status,
                created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("tool_exec_new", "session-1", "memory.search", "success", new_time),
        )

    async def run() -> None:
        await init_engine(database_runtime.database_path())
        try:
            deleted = await AIRetentionService().cleanup_tool_executions(
                retention_days=1
            )
            assert deleted == 1
        finally:
            await close_engine()

    asyncio.run(run())

    with database_runtime.connect_sync() as connection:
        rows = connection.execute(
            "SELECT execution_id FROM ai_tool_execution ORDER BY execution_id"
        ).fetchall()
    assert rows == [("tool_exec_new",)]


def _seed_chat_session(session_id: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with database_runtime.connect_sync() as connection:
        connection.execute(
            """
            INSERT INTO chat_session (
                session_id,
                platform,
                bot_id,
                scene_type,
                scene_id,
                created_at,
                updated_at,
                last_message_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                "onebot",
                "bot-1",
                "private",
                "user-1",
                timestamp,
                timestamp,
                timestamp,
            ),
        )

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apeiria.db.runtime import database_runtime
from apeiria.webui.auth import require_control_panel

HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
MEASURED_INPUT_TOKENS = 10
MEASURED_OUTPUT_TOKENS = 5
MEASURED_TOTAL_TOKENS = 15
EXPECTED_SESSION_USAGE_CALL_COUNT = 2

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_ai_usage_routes_require_control_panel(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.webui.routes.ai import router

    app = FastAPI()
    app.include_router(router, prefix="/ai")
    client = TestClient(app)

    response = client.get("/ai/usage-events")

    assert response.status_code == HTTP_UNAUTHORIZED


def test_ai_usage_routes_filter_and_group_events(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    _seed_usage_events()

    from apeiria.webui.routes.ai import router

    app = FastAPI()
    app.dependency_overrides[require_control_panel] = _control_panel_override
    app.include_router(router, prefix="/ai")
    client = TestClient(app)

    events = client.get(
        "/ai/usage-events",
        params={
            "session_id": "session-1",
            "model_name": "gpt-test",
            "limit": 10,
        },
    )
    summary = client.get(
        "/ai/usage-summary",
        params={
            "group_by": "response_source",
            "session_id": "session-1",
        },
    )

    assert events.status_code == HTTP_OK
    event_payload = events.json()
    assert [event["trace_id"] for event in event_payload] == ["trace-2", "trace-1"]
    assert event_payload[0]["usage_available"] is False
    assert event_payload[1]["input_tokens"] == MEASURED_INPUT_TOKENS
    assert event_payload[1]["provider_usage"] == {
        "completion_tokens": MEASURED_OUTPUT_TOKENS,
        "prompt_tokens": MEASURED_INPUT_TOKENS,
        "total_tokens": MEASURED_TOTAL_TOKENS,
    }
    assert summary.status_code == HTTP_OK
    summary_payload = {item["group_key"]: item for item in summary.json()}
    assert summary_payload["direct"]["call_count"] == 1
    assert summary_payload["direct"]["total_tokens"] == MEASURED_TOTAL_TOKENS
    assert summary_payload["tool_loop"]["missing_usage_count"] == 1


def test_trace_and_managed_session_responses_include_usage_totals(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.app.ai.runtime.session.identity import (
        derive_ai_session_source_identity,
    )
    from apeiria.app.ai.runtime.trace import TurnTrace, TurnTraceRepository
    from apeiria.app.ai.sessions.repository import AISessionManagementRepository
    from apeiria.conversation.models import ChatSessionIdentity
    from apeiria.webui.routes.ai import router

    identity = ChatSessionIdentity(
        session_id="session-1",
        platform="onebot",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )
    asyncio.run(
        AISessionManagementRepository().ensure_session(
            derive_ai_session_source_identity(identity)
        )
    )
    TurnTraceRepository().store_trace(
        TurnTrace(
            trace_id="trace-1",
            session_id="session-1",
            runtime_mode="message",
            strategy_action="reply",
            final_response_source="direct",
        )
    )
    _seed_usage_events()

    app = FastAPI()
    app.dependency_overrides[require_control_panel] = _control_panel_override
    app.include_router(router, prefix="/ai")
    client = TestClient(app)

    trace = client.get("/ai/traces/trace-1")
    session = client.get("/ai/managed-sessions/session-1")

    assert trace.status_code == HTTP_OK
    assert trace.json()["usage"]["total_tokens"] == MEASURED_TOTAL_TOKENS
    assert trace.json()["usage"]["missing_usage_count"] == 0
    assert trace.json()["usage_events"][0]["trace_id"] == "trace-1"
    assert session.status_code == HTTP_OK
    assert session.json()["usage"]["call_count"] == EXPECTED_SESSION_USAGE_CALL_COUNT
    assert session.json()["usage"]["total_tokens"] == MEASURED_TOTAL_TOKENS
    assert session.json()["usage"]["missing_usage_count"] == 1


def test_trace_response_includes_no_usage_state(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.app.ai.runtime.trace import TurnTrace, TurnTraceRepository
    from apeiria.webui.routes.ai import router

    TurnTraceRepository().store_trace(
        TurnTrace(
            trace_id="trace-empty",
            session_id="session-empty",
            runtime_mode="message",
            strategy_action="reply",
            final_response_source="direct",
        )
    )

    app = FastAPI()
    app.dependency_overrides[require_control_panel] = _control_panel_override
    app.include_router(router, prefix="/ai")
    client = TestClient(app)

    response = client.get("/ai/traces/trace-empty")

    assert response.status_code == HTTP_OK
    assert response.json()["usage"]["call_count"] == 0
    assert response.json()["usage"]["usage_available"] is False
    assert response.json()["usage_events"] == []


def _seed_usage_events() -> None:
    from apeiria.ai.token_usage import (
        AIModelUsageCreateInput,
        AIModelUsageRepository,
        normalize_provider_usage,
    )

    repository = AIModelUsageRepository()
    created_at = datetime(2026, 5, 17, 10, 0, tzinfo=timezone.utc)
    repository.record_usage(
        AIModelUsageCreateInput(
            trace_id="trace-1",
            session_id="session-1",
            runtime_mode="message",
            response_source="direct",
            source_id="source-1",
            model_name="gpt-test",
            operation="chat_generation",
            attempt_index=1,
            status="success",
            provider_response_id="resp-1",
            finish_reason="stop",
            usage=normalize_provider_usage(
                adapter_kind="openai_compatible",
                usage={
                    "prompt_tokens": MEASURED_INPUT_TOKENS,
                    "completion_tokens": MEASURED_OUTPUT_TOKENS,
                    "total_tokens": MEASURED_TOTAL_TOKENS,
                },
            ),
            created_at=created_at,
        )
    )
    repository.record_usage(
        AIModelUsageCreateInput(
            trace_id="trace-2",
            session_id="session-1",
            runtime_mode="message",
            response_source="tool_loop",
            source_id="source-1",
            model_name="gpt-test",
            operation="chat_generation",
            attempt_index=2,
            status="empty_response",
            usage=normalize_provider_usage(
                adapter_kind="openai_compatible",
                usage=None,
            ),
            created_at=created_at,
        )
    )


def _control_panel_override() -> object:
    return object()

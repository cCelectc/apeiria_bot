from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apeiria.db.runtime import database_runtime
from apeiria.webui.auth import require_control_panel

HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
EXPECTED_MANAGED_SESSION_COUNT = 1

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_ai_managed_session_routes_require_control_panel(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.webui.routes.ai import router

    app = FastAPI()
    app.include_router(router, prefix="/ai")
    client = TestClient(app)

    response = client.get("/ai/managed-sessions")

    assert response.status_code == HTTP_UNAUTHORIZED


def test_ai_managed_session_routes_manage_v1_state(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.persona.models import AIPersonaCreateInput
    from apeiria.ai.persona.service import ai_persona_service
    from apeiria.app.ai.runtime.session.identity import (
        derive_ai_session_source_identity,
    )
    from apeiria.app.ai.sessions.repository import AISessionManagementRepository
    from apeiria.conversation.contracts import ChatMessageCreate
    from apeiria.conversation.models import ChatSessionIdentity
    from apeiria.conversation.service import chat_session_service
    from apeiria.webui.routes.ai import router

    identity = ChatSessionIdentity(
        session_id="onebot:bot-1:private:user-1",
        platform="onebot",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )

    async def seed() -> str:
        persona = await ai_persona_service.create_persona(
            AIPersonaCreateInput(
                name="Operator",
                description="Operator persona",
                system_prompt="Be precise.",
                style_prompt="Brief.",
            )
        )
        await chat_session_service.append_message(
            identity,
            ChatMessageCreate(
                author_role="user",
                author_id="user-1",
                text_content="hello",
            ),
        )
        await AISessionManagementRepository().ensure_session(
            derive_ai_session_source_identity(identity)
        )
        return persona.persona_id

    persona_id = asyncio.run(seed())

    def dependency_override() -> object:
        return object()

    app = FastAPI()
    app.dependency_overrides[require_control_panel] = dependency_override
    app.include_router(router, prefix="/ai")
    client = TestClient(app)

    listed = client.get("/ai/managed-sessions")
    assert listed.status_code == HTTP_OK
    listed_payload = listed.json()
    assert len(listed_payload) == EXPECTED_MANAGED_SESSION_COUNT
    assert listed_payload[0]["session_id"] == identity.session_id
    assert listed_payload[0]["ai_enabled"] is True

    disabled = client.patch(
        f"/ai/managed-sessions/{identity.session_id}/ai-enabled",
        json={"ai_enabled": False},
    )
    assert disabled.status_code == HTTP_OK
    assert disabled.json()["ai_enabled"] is False

    persona_update = client.patch(
        f"/ai/managed-sessions/{identity.session_id}/persona",
        json={"persona_id": persona_id},
    )
    assert persona_update.status_code == HTTP_OK
    assert persona_update.json()["persona"]["persona_id"] == persona_id

    reset = client.post(f"/ai/managed-sessions/{identity.session_id}/context-reset")
    assert reset.status_code == HTTP_OK
    assert reset.json()["reset_boundary_at"] is not None

    detail = client.get(f"/ai/managed-sessions/{identity.session_id}")
    assert detail.status_code == HTTP_OK
    assert detail.json()["session_id"] == identity.session_id
    assert detail.json()["persona"]["name"] == "Operator"

    missing = client.get("/ai/managed-sessions/missing")
    assert missing.status_code == HTTP_NOT_FOUND

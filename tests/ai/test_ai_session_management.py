from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pytest import raises

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_managed_session_repository_creates_and_updates_records(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.app.ai.sessions.models import (
        AISessionManagementUpdate,
        AISessionSourceIdentity,
        NormalizedAISessionIdentity,
    )
    from apeiria.app.ai.sessions.repository import AISessionManagementRepository

    identity = NormalizedAISessionIdentity(
        session_id="onebot:group:group-1",
        platform_id="onebot",
        platform_type="onebot_v11",
        message_type="group",
        subject_id="group-1",
    )
    source = AISessionSourceIdentity(
        identity=identity,
        source_labels={"group": "Ops"},
        diagnostic_raw_ids={"bot_id": "bot-1"},
    )
    repository = AISessionManagementRepository()

    async def scenario() -> None:
        created = await repository.ensure_session(source)
        updated = await repository.update_session(
            session_id=created.session_id,
            update=AISessionManagementUpdate(
                ai_enabled=False,
                persona_id=None,
                actor_id="admin-1",
            ),
        )
        reset = await repository.mark_context_reset(
            session_id=created.session_id,
            actor_id="admin-2",
        )
        loaded = await repository.get_session(created.session_id)

        assert created.session_id == "onebot:group:group-1"
        assert created.ai_enabled is True
        assert created.persona_id is None
        assert created.source_identity.source_labels == {"group": "Ops"}
        assert updated is not None
        assert updated.ai_enabled is False
        assert updated.audit_updated_by == "admin-1"
        assert reset is not None
        assert reset.context_reset_at is not None
        assert reset.context_reset_by == "admin-2"
        assert loaded == reset

    asyncio.run(scenario())


def test_managed_session_repository_validates_persona_reference(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.app.ai.sessions.models import (
        AISessionManagementUpdate,
        AISessionSourceIdentity,
        NormalizedAISessionIdentity,
        UnknownAISessionPersonaError,
    )
    from apeiria.app.ai.sessions.repository import AISessionManagementRepository

    identity = NormalizedAISessionIdentity(
        session_id="onebot:private:user-1",
        platform_id="onebot",
        platform_type="onebot_v11",
        message_type="private",
        subject_id="user-1",
    )
    repository = AISessionManagementRepository()

    async def scenario() -> None:
        await repository.ensure_session(AISessionSourceIdentity(identity=identity))
        with raises(UnknownAISessionPersonaError):
            await repository.update_session(
                session_id=identity.session_id,
                update=AISessionManagementUpdate(
                    persona_id="persona_missing",
                    actor_id="admin-1",
                ),
            )

    asyncio.run(scenario())


def test_managed_session_repository_persists_persona_override(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.persona.models import AIPersonaCreateInput
    from apeiria.ai.persona.service import ai_persona_service
    from apeiria.app.ai.sessions.models import (
        AISessionManagementUpdate,
        AISessionSourceIdentity,
        NormalizedAISessionIdentity,
    )
    from apeiria.app.ai.sessions.repository import AISessionManagementRepository

    identity = NormalizedAISessionIdentity(
        session_id="webchat:web_chat:web-session-1",
        platform_id="webchat",
        platform_type="web_chat",
        message_type="web_chat",
        subject_id="web-session-1",
    )
    repository = AISessionManagementRepository()

    async def scenario() -> None:
        persona = await ai_persona_service.create_persona(
            AIPersonaCreateInput(
                name="Operator",
                description="Operator persona",
                system_prompt="Be precise.",
                style_prompt="Brief.",
            )
        )
        await repository.ensure_session(AISessionSourceIdentity(identity=identity))
        updated = await repository.update_session(
            session_id=identity.session_id,
            update=AISessionManagementUpdate(
                persona_id=persona.persona_id,
                actor_id="admin-1",
            ),
        )
        cleared = await repository.update_session(
            session_id=identity.session_id,
            update=AISessionManagementUpdate(
                persona_id=None,
                actor_id="admin-2",
            ),
        )

        assert updated is not None
        assert updated.persona_id == persona.persona_id
        assert cleared is not None
        assert cleared.persona_id is None
        assert cleared.audit_updated_by == "admin-2"

    asyncio.run(scenario())


def test_ai_session_validation_rejects_unsupported_shapes() -> None:
    from apeiria.app.ai.sessions.models import (
        AISessionManagementUpdate,
        AISessionValidationError,
        NormalizedAISessionIdentity,
        validate_session_management_payload,
    )

    with raises(AISessionValidationError, match="session_id"):
        NormalizedAISessionIdentity(
            session_id="../bad",
            platform_id="onebot",
            platform_type="onebot_v11",
            message_type="group",
            subject_id="group-1",
        )

    with raises(AISessionValidationError, match="origin"):
        validate_session_management_payload(
            {
                "ai_enabled": True,
                "origin_rule": {"group": "*"},
            }
        )

    with raises(AISessionValidationError, match="multi-conversation"):
        validate_session_management_payload(
            {
                "ai_enabled": True,
                "conversation_ids": ["conv-1", "conv-2"],
            }
        )

    update = AISessionManagementUpdate.from_payload(
        {
            "ai_enabled": False,
            "persona_id": "",
            "actor_id": "admin-1",
        }
    )
    assert update.ai_enabled is False
    assert update.persona_id is None

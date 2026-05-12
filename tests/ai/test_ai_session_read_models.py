from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch

EXPECTED_MESSAGE_COUNT = 2


def test_session_inventory_and_detail_include_management_state(
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
    from apeiria.app.ai.runtime.trace import (
        TurnTrace,
        TurnTraceRepository,
        datetime_to_text,
    )
    from apeiria.app.ai.sessions.management import AISessionManagementReader
    from apeiria.app.ai.sessions.models import AISessionManagementUpdate
    from apeiria.app.ai.sessions.repository import AISessionManagementRepository
    from apeiria.conversation.contracts import ChatMessageCreate
    from apeiria.conversation.models import ChatSessionIdentity
    from apeiria.conversation.service import chat_session_service

    identity = ChatSessionIdentity(
        session_id="onebot:bot-1:private:user-1",
        platform="onebot",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )
    reset_at = datetime(2026, 5, 12, 2, 0, tzinfo=timezone.utc)

    async def scenario() -> None:
        persona = await ai_persona_service.create_persona(
            AIPersonaCreateInput(
                name="Operator",
                description="Operator persona",
                system_prompt="Be precise.",
                style_prompt="Brief.",
            )
        )
        before_message = await chat_session_service.append_message(
            identity,
            ChatMessageCreate(
                author_role="user",
                author_id="user-1",
                text_content="before reset",
            ),
        )
        after_message = await chat_session_service.append_message(
            identity,
            ChatMessageCreate(
                author_role="assistant",
                author_id="bot-1",
                text_content="after reset",
                meta={"trace_id": "trace-1", "model_name": "gpt-test"},
            ),
        )
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE chat_message
                SET created_at = ?
                WHERE message_id = ?
                """,
                (
                    datetime_to_text(datetime(2026, 5, 12, 1, 0, tzinfo=timezone.utc)),
                    before_message.message_id,
                ),
            )
            connection.execute(
                """
                UPDATE chat_message
                SET created_at = ?
                WHERE message_id = ?
                """,
                (
                    datetime_to_text(datetime(2026, 5, 12, 3, 0, tzinfo=timezone.utc)),
                    after_message.message_id,
                ),
            )
        repository = AISessionManagementRepository()
        await repository.ensure_session(
            derive_ai_session_source_identity(
                identity,
                source_labels={"chat": "Alice"},
            )
        )
        await repository.update_session(
            session_id=identity.session_id,
            update=AISessionManagementUpdate(
                ai_enabled=False,
                persona_id=persona.persona_id,
                actor_id="admin-1",
            ),
        )
        await repository.mark_context_reset(
            session_id=identity.session_id,
            actor_id="admin-1",
            reset_at=reset_at,
        )
        TurnTraceRepository().store_trace(
            TurnTrace(
                trace_id="trace-1",
                session_id=identity.session_id,
                runtime_mode="message",
                strategy_action="observe",
                strategy_reason_codes=("session_ai_disabled",),
                skip_reason="session_ai_disabled",
            )
        )
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE ai_managed_session
                SET context_reset_at = ?
                WHERE session_id = ?
                """,
                (datetime_to_text(reset_at), identity.session_id),
            )

        reader = AISessionManagementReader()
        sessions = await reader.list_sessions(limit=10)
        detail = await reader.get_session_detail(
            session_id=identity.session_id,
            message_limit=10,
        )

        assert len(sessions) == 1
        assert sessions[0].session_id == identity.session_id
        assert sessions[0].ai_enabled is False
        assert sessions[0].persona is not None
        assert sessions[0].persona.name == "Operator"
        assert sessions[0].message_count == EXPECTED_MESSAGE_COUNT
        assert sessions[0].source_labels["chat"] == "Alice"
        assert detail is not None
        assert detail.reset_boundary_at == reset_at
        assert [message.text_content for message in detail.recent_messages] == [
            "before reset",
            "after reset",
        ]
        assert detail.recent_messages[0].before_reset_boundary is True
        assert detail.recent_messages[1].before_reset_boundary is False
        assert detail.prompt_preview_entry.session_id == identity.session_id
        assert detail.trace_entries[0].trace_id == "trace-1"
        assert detail.model_summary["last_model_name"] == "gpt-test"
        assert detail.diagnostics["skipped_reply_reason"] == "session_ai_disabled"

    asyncio.run(scenario())


def test_prompt_preview_includes_session_management_state(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.app.ai.runtime.session.identity import (
        derive_ai_session_source_identity,
    )
    from apeiria.app.ai.sessions.models import AISessionManagementUpdate
    from apeiria.app.ai.sessions.prompt_preview import build_scene_prompt_preview
    from apeiria.app.ai.sessions.repository import AISessionManagementRepository
    from apeiria.conversation.contracts import ChatMessageCreate
    from apeiria.conversation.models import ChatSessionIdentity
    from apeiria.conversation.service import chat_session_service

    identity = ChatSessionIdentity(
        session_id="onebot:bot-1:private:user-1",
        platform="onebot",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )

    async def scenario() -> None:
        await chat_session_service.append_message(
            identity,
            ChatMessageCreate(
                author_role="user",
                author_id="user-1",
                text_content="hello",
            ),
        )
        repository = AISessionManagementRepository()
        await repository.ensure_session(derive_ai_session_source_identity(identity))
        await repository.update_session(
            session_id=identity.session_id,
            update=AISessionManagementUpdate(ai_enabled=False, actor_id="admin-1"),
        )

        preview = await build_scene_prompt_preview(scene_id=identity.session_id)

        assert preview is not None
        assert "session_ai_disabled" in preview.preview_diagnostics
        assert "session_ai_enabled:false" in preview.preview_diagnostics
        assert preview.hard_rule_reason_codes == ("session_ai_disabled",)
        assert preview.rendered_prompt == "AI replies are disabled for this session."

    asyncio.run(scenario())

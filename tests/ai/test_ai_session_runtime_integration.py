from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.conversation.models import ChatContextMessageView, ChatSessionIdentity
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_runtime_derives_managed_session_identity_from_chat_identity() -> None:
    from apeiria.app.ai.runtime.session.identity import (
        derive_ai_session_source_identity,
    )

    group = ChatSessionIdentity(
        session_id="onebot:bot-1:group:group-1",
        platform="onebot",
        bot_id="bot-1",
        scene_type="group",
        scene_id="group-1",
        subject_id=None,
    )
    private = ChatSessionIdentity(
        session_id="onebot:bot-1:private:user-1",
        platform="onebot",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )
    web_chat = ChatSessionIdentity(
        session_id="webchat:session-1",
        platform="webchat",
        bot_id="web",
        scene_type="private",
        scene_id="session-1",
        subject_id="session-1",
    )

    group_source = derive_ai_session_source_identity(group)
    private_source = derive_ai_session_source_identity(private)
    web_source = derive_ai_session_source_identity(web_chat, platform_type="web_chat")

    assert group_source.identity.message_type == "group"
    assert group_source.identity.subject_id == "group-1"
    assert group_source.diagnostic_raw_ids["bot_id"] == "bot-1"
    assert private_source.identity.message_type == "private"
    assert private_source.identity.subject_id == "user-1"
    assert web_source.identity.message_type == "web_chat"
    assert web_source.identity.subject_id == "session-1"


def test_policy_skips_disabled_managed_session(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.app.ai.reply_strategy.models import WakeContext
    from apeiria.app.ai.runtime.policy import RuntimePolicyDecisionStage
    from apeiria.app.ai.runtime.session.context import (
        RuntimeTurnInput,
        RuntimeTurnSource,
    )
    from apeiria.app.ai.runtime.session.identity import (
        derive_ai_session_source_identity,
    )
    from apeiria.app.ai.runtime.stages import RuntimeIngressInput
    from apeiria.app.ai.sessions.models import AISessionManagementUpdate
    from apeiria.app.ai.sessions.repository import AISessionManagementRepository

    identity = ChatSessionIdentity(
        session_id="onebot:bot-1:private:user-1",
        platform="onebot",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )

    async def never_decide(**_: object) -> None:
        raise _UnexpectedReplyDecisionError

    async def scenario() -> None:
        repository = AISessionManagementRepository()
        await repository.ensure_session(derive_ai_session_source_identity(identity))
        await repository.update_session(
            session_id=identity.session_id,
            update=AISessionManagementUpdate(ai_enabled=False, actor_id="admin-1"),
        )
        turn = RuntimeTurnInput(
            identity=identity,
            source=RuntimeTurnSource(
                runtime_mode="message",
                message_text="hello",
                source_message_id="message-1",
                user_id="user-1",
                is_private=True,
            ),
            sender_id="user-1",
        )
        policy = RuntimePolicyDecisionStage(reply_decider=never_decide)
        outcome = policy.evaluate(
            ingress_input=RuntimeIngressInput(
                stage="ingress",
                turn=turn,
                current_time=datetime(2026, 5, 12, tzinfo=timezone.utc),
                wake_context=WakeContext(
                    bot_self_id="bot-1",
                    user_id="user-1",
                    message_text="hello",
                    is_tome=False,
                    is_private=True,
                    is_future_task=False,
                ),
            )
        )

        assert outcome.should_continue is False
        assert outcome.decision.reason_codes == ("session_ai_disabled",)
        assert outcome.decision.evidence["session_id"] == identity.session_id

    asyncio.run(scenario())


def test_session_persona_override_precedes_default_binding(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.persona.models import AIPersonaCreateInput
    from apeiria.ai.persona.service import ai_persona_service
    from apeiria.app.ai.runtime.context.personas import load_persona_bundle
    from apeiria.app.ai.runtime.session.context import (
        RuntimeTurnInput,
        RuntimeTurnSource,
    )
    from apeiria.app.ai.runtime.session.identity import (
        derive_ai_session_source_identity,
    )
    from apeiria.app.ai.sessions.models import AISessionManagementUpdate
    from apeiria.app.ai.sessions.repository import AISessionManagementRepository

    identity = ChatSessionIdentity(
        session_id="onebot:bot-1:group:group-1",
        platform="onebot",
        bot_id="bot-1",
        scene_type="group",
        scene_id="group-1",
        subject_id=None,
    )

    async def scenario() -> None:
        default_persona = await ai_persona_service.create_persona(
            AIPersonaCreateInput(
                name="Default",
                description="Default",
                system_prompt="Default persona",
                style_prompt="Default style",
            )
        )
        override_persona = await ai_persona_service.create_persona(
            AIPersonaCreateInput(
                name="Override",
                description="Override",
                system_prompt="Override persona",
                style_prompt="Override style",
            )
        )
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                INSERT INTO ai_persona_binding (
                    binding_id,
                    scope_type,
                    scope_id,
                    persona_id,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "binding-1",
                    "conversation",
                    identity.session_id,
                    default_persona.persona_id,
                    "2026-05-12T00:00:00+00:00",
                ),
            )
        repository = AISessionManagementRepository()
        await repository.ensure_session(derive_ai_session_source_identity(identity))
        await repository.update_session(
            session_id=identity.session_id,
            update=AISessionManagementUpdate(
                persona_id=override_persona.persona_id,
                actor_id="admin-1",
            ),
        )
        turn = RuntimeTurnInput(
            identity=identity,
            source=RuntimeTurnSource(
                runtime_mode="message",
                message_text="hello",
                source_message_id="message-1",
                user_id="user-1",
            ),
            sender_id="user-1",
        )

        bundle = await load_persona_bundle(
            turn=turn,
            current_time=datetime(2026, 5, 12, tzinfo=timezone.utc),
            turns=[],
        )

        assert bundle is not None
        assert bundle.persona_id == override_persona.persona_id
        assert bundle.system_prompt == "Override persona"

    asyncio.run(scenario())


def test_context_reset_filters_earlier_turns(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    import apeiria.app.ai.runtime.context.context_window as context_window_module
    from apeiria.app.ai.runtime.context.materials import collect_conversation_context
    from apeiria.app.ai.runtime.session.context import (
        RuntimeTurnInput,
        RuntimeTurnSource,
    )
    from apeiria.app.ai.runtime.session.identity import (
        derive_ai_session_source_identity,
    )
    from apeiria.app.ai.sessions.repository import AISessionManagementRepository

    identity = ChatSessionIdentity(
        session_id="onebot:bot-1:private:user-1",
        platform="onebot",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )
    before_reset = datetime(2026, 5, 12, 1, 0, tzinfo=timezone.utc)
    reset_at = datetime(2026, 5, 12, 2, 0, tzinfo=timezone.utc)
    after_reset = datetime(2026, 5, 12, 3, 0, tzinfo=timezone.utc)
    messages = [
        _context_message("old", created_at=before_reset),
        _context_message("new", created_at=after_reset),
    ]
    stored_summaries: list[str | None] = []

    class ChatSessionServiceStub:
        async def list_recent_messages(
            self,
            _identity: ChatSessionIdentity,
            *,
            max_messages: int,
        ) -> list[ChatContextMessageView]:
            del max_messages
            return list(messages)

        async def load_session_summary(
            self,
            _identity: ChatSessionIdentity,
        ) -> str | None:
            return "old summary"

        async def store_summary_text(
            self,
            _identity: ChatSessionIdentity,
            *,
            summary: str | None,
        ) -> None:
            stored_summaries.append(summary)

    monkeypatch.setattr(
        context_window_module,
        "chat_session_service",
        ChatSessionServiceStub(),
    )

    async def scenario() -> None:
        repository = AISessionManagementRepository()
        await repository.ensure_session(derive_ai_session_source_identity(identity))
        await repository.mark_context_reset(
            session_id=identity.session_id,
            actor_id="admin-1",
            reset_at=reset_at,
        )
        context = await collect_conversation_context(
            RuntimeTurnInput(
                identity=identity,
                source=RuntimeTurnSource(
                    runtime_mode="message",
                    message_text="hello",
                    source_message_id="message-2",
                    user_id="user-1",
                    is_private=True,
                ),
                sender_id="user-1",
            )
        )

        assert [turn.text_content for turn in context.turns] == ["new"]
        assert stored_summaries == ["User: new"]

    asyncio.run(scenario())


def _context_message(
    text: str,
    *,
    created_at: datetime,
) -> ChatContextMessageView:
    return ChatContextMessageView(
        message_id=f"message-{text}",
        author_role="user",
        author_id="user-1",
        author_name=None,
        text_content=text,
        content=None,
        created_at=created_at,
    )


class _UnexpectedReplyDecisionError(RuntimeError):
    """Raised if disabled-session policy allows reply judgment to continue."""

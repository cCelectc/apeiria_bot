from __future__ import annotations

import asyncio
import importlib
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_import_ai_admin_personas_does_not_require_nonebot_runtime() -> None:
    sys.modules.pop("apeiria.ai.admin.personas", None)

    module = importlib.import_module("apeiria.ai.admin.personas")

    assert module.__name__ == "apeiria.ai.admin.personas"


def test_personas_admin_and_service_use_new_database(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.ai.admin.personas import PersonasAdminMixin
    from apeiria.ai.persona.models import AIPersonaBindingTarget
    from apeiria.ai.persona.service import (
        AIPersonaRenderContext,
        ai_persona_service,
    )

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    admin = PersonasAdminMixin()

    async def run() -> None:
        created = await admin.create_persona(
            name="Guide",
            description="Helpful",
            system_prompt="Hello {user_name}",
            style_prompt="Tone {scene_label}",
            enabled=True,
        )
        personas = await admin.list_personas()
        assert len(personas) == 1
        assert personas[0].persona_id == created.persona_id

        updated = await admin.update_persona(
            persona_id=created.persona_id,
            name="Guide Updated",
            description="More Helpful",
            system_prompt="Hi {user_name}",
            style_prompt="Mood {scene_label}",
            enabled=True,
        )
        assert updated is not None
        assert updated.name == "Guide Updated"
        assert updated.enabled is True
        assert await admin.list_persona_bindings() == []

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
                    "bind-1",
                    "conversation",
                    "conversation-1",
                    created.persona_id,
                    "2026-04-25T00:00:00",
                ),
            )

        resolved = await ai_persona_service.resolve_persona(
            None,
            target=AIPersonaBindingTarget(
                conversation_id="conversation-1",
                group_id=None,
                user_id=None,
            ),
        )
        assert resolved is not None
        assert resolved.persona_id == created.persona_id

        bundle = await ai_persona_service.build_persona_prompt_bundle(
            None,
            target=AIPersonaBindingTarget(
                conversation_id="conversation-1",
                group_id=None,
                user_id=None,
            ),
            render_context=AIPersonaRenderContext(
                bot_name="Apeiria",
                bot_id="apeiria",
                current_time=datetime.now(timezone.utc),
                platform="test",
                scene_type="private",
                scene_id="conversation-1",
                session_id="session-1",
                scene_label="Private Chat",
                user_name="Alice",
                is_private_chat=True,
            ),
        )
        assert bundle is not None
        assert "Alice" in bundle.system_prompt

    asyncio.run(run())

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_tool_policy_bindings_use_control_plane_sqlite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.tools.policy import (
        AIToolLevel,
        AIToolPolicyBindingTarget,
        AIToolSceneContext,
        ai_tool_policy_binding_service,
    )
    from apeiria.app.ai.operations import tools as operations_tools

    audit_events: list[tuple[str, str | None, str | None]] = []
    monkeypatch.setattr(
        operations_tools,
        "record_ai_admin_audit",
        lambda event_type, *, actor_username=None, detail=None: audit_events.append(
            (event_type, actor_username, detail)
        ),
    )

    class _Operations(operations_tools.ToolsAdminMixin):
        pass

    operations = _Operations()

    async def scenario() -> None:
        global_binding = await operations.create_tool_policy_binding(
            scope_type="global",
            scope_id="__global__",
            allowed_level=AIToolLevel.READ,
            actor_username="alice",
        )
        group_binding = await operations.create_tool_policy_binding(
            scope_type="group",
            scope_id="group-1",
            allowed_level=AIToolLevel.NONE,
            actor_username="alice",
        )
        user_binding = await operations.create_tool_policy_binding(
            scope_type="user",
            scope_id="user-1",
            allowed_level=AIToolLevel.HOST,
            actor_username="alice",
        )

        listed = await operations.list_tool_policy_bindings()

        assert [item.binding_id for item in listed] == [
            global_binding.binding_id,
            group_binding.binding_id,
            user_binding.binding_id,
        ]

        updated_global = await operations.update_tool_policy_binding(
            binding_id=global_binding.binding_id,
            allowed_level=AIToolLevel.WRITE,
            actor_username="alice",
        )

        assert updated_global is not None
        assert updated_global.allowed_level is AIToolLevel.WRITE

        user_policy = await ai_tool_policy_binding_service.resolve_scene_policy(
            scene_context=AIToolSceneContext(scope_type="private", is_tome=False),
            target=AIToolPolicyBindingTarget(
                conversation_id="conv-1",
                group_id="group-1",
                user_id="user-1",
            ),
        )

        assert user_policy.allowed_level is AIToolLevel.HOST

        deleted = await operations.delete_tool_policy_binding(
            binding_id=user_binding.binding_id,
            actor_username="alice",
        )

        assert deleted is True

        group_policy = await ai_tool_policy_binding_service.resolve_scene_policy(
            scene_context=AIToolSceneContext(scope_type="private", is_tome=False),
            target=AIToolPolicyBindingTarget(
                conversation_id="conv-1",
                group_id="group-1",
                user_id="user-1",
            ),
        )

        assert group_policy.allowed_level is AIToolLevel.NONE
        assert (
            await operations.delete_tool_policy_binding(binding_id="missing") is False
        )

    asyncio.run(scenario())

    assert [event[0] for event in audit_events] == [
        "ai_tool_policy_binding_created",
        "ai_tool_policy_binding_created",
        "ai_tool_policy_binding_created",
        "ai_tool_policy_binding_updated",
        "ai_tool_policy_binding_deleted",
    ]

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import HTTPException

from apeiria.access.principal import AuthSession, Principal, PrincipalRole
from apeiria.access.principal_roles import CAP_CONTROL_PANEL
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403
DEFAULT_TOOL_TIMEOUT_SECONDS = 8.0
UPDATED_TOOL_TIMEOUT_SECONDS = 2.5


def test_ai_runtime_settings_routes_read_and_update(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.webui.routes.ai.settings import (
        get_ai_runtime_settings,
        update_ai_runtime_settings,
    )
    from apeiria.webui.routes.ai.settings_schemas import (
        AIRuntimeSettingsUpdateRequest,
    )

    async def scenario() -> None:
        initial = await get_ai_runtime_settings(_control_panel_session())
        assert (
            initial.effective["tool_execution_timeout_seconds"]
            == DEFAULT_TOOL_TIMEOUT_SECONDS
        )
        assert initial.overrides == {}
        assert any(
            item.key == "tool_execution_timeout_seconds"
            and item.default_value == DEFAULT_TOOL_TIMEOUT_SECONDS
            for item in initial.fields
        )

        updated = await update_ai_runtime_settings(
            AIRuntimeSettingsUpdateRequest(
                values={
                    "allow_group_initiative": True,
                    "tool_execution_timeout_seconds": UPDATED_TOOL_TIMEOUT_SECONDS,
                }
            ),
            _control_panel_session(),
        )

        assert updated.effective["allow_group_initiative"] is True
        assert (
            updated.effective["tool_execution_timeout_seconds"]
            == UPDATED_TOOL_TIMEOUT_SECONDS
        )
        assert updated.overrides == {
            "allow_group_initiative": True,
            "tool_execution_timeout_seconds": UPDATED_TOOL_TIMEOUT_SECONDS,
        }

        cleared = await update_ai_runtime_settings(
            AIRuntimeSettingsUpdateRequest(clear=["allow_group_initiative"]),
            _control_panel_session(),
        )

        assert cleared.effective["allow_group_initiative"] is False
        assert cleared.overrides == {
            "tool_execution_timeout_seconds": UPDATED_TOOL_TIMEOUT_SECONDS
        }

    import asyncio

    asyncio.run(scenario())


def test_ai_runtime_settings_route_rejects_invalid_update(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.webui.routes.ai.settings import update_ai_runtime_settings
    from apeiria.webui.routes.ai.settings_schemas import (
        AIRuntimeSettingsUpdateRequest,
    )

    async def scenario() -> None:
        with pytest.raises(HTTPException) as exc_info:
            await update_ai_runtime_settings(
                AIRuntimeSettingsUpdateRequest(
                    values={"conversation_retention_days": -1}
                ),
                _control_panel_session(),
            )
        assert exc_info.value.status_code == HTTP_BAD_REQUEST

    import asyncio

    asyncio.run(scenario())


def test_require_control_panel_rejects_session_without_capability() -> None:
    from apeiria.webui.auth import require_control_panel

    async def scenario() -> None:
        with pytest.raises(HTTPException) as exc_info:
            await require_control_panel(_plain_session())

        assert exc_info.value.status_code == HTTP_FORBIDDEN

    import asyncio

    asyncio.run(scenario())


def _control_panel_session() -> AuthSession:
    return AuthSession(
        principal=Principal(
            principal_kind="webui_account",
            principal_id="admin",
            display_name="admin",
            role=PrincipalRole(
                role_id="owner",
                capabilities=(CAP_CONTROL_PANEL,),
            ),
        ),
        auth_method="password",
        session_version=1,
        token_subject="admin",
    )


def _plain_session() -> AuthSession:
    return AuthSession(
        principal=Principal(
            principal_kind="webui_account",
            principal_id="viewer",
            display_name="viewer",
            role=PrincipalRole(role_id="viewer", capabilities=()),
        ),
        auth_method="password",
        session_version=1,
        token_subject="viewer",
    )

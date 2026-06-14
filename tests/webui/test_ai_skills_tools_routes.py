from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING

from apeiria.access.principal import AuthSession, Principal, PrincipalRole

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def _auth_session() -> AuthSession:
    return AuthSession(
        principal=Principal(
            principal_kind="webui_account",
            principal_id="admin",
            display_name="admin",
            role=PrincipalRole(
                role_id="webui_local_account",
                capabilities=("control_panel",),
            ),
        ),
        auth_method="password",
        session_version=1,
        token_subject="admin",
    )


def test_ai_skill_routes_list_and_reload(monkeypatch: "MonkeyPatch") -> None:
    from apeiria.webui.routes.ai.skills import (
        ai_application,
        list_ai_skills,
        reload_ai_skills,
    )

    monkeypatch.setattr(
        ai_application._skills,
        "_entry",
        SimpleNamespace(
            list_skills=lambda: [
                SimpleNamespace(
                    name="skill-alpha",
                    description="Alpha",
                    display_name="skill-alpha",
                    display_description="Alpha",
                    entry_mode="prompt_only",
                    tags=("ops",),
                    source_path="/tmp/skill-alpha/SKILL.md",
                    required_tools=("tool_a",),
                    loaded=True,
                    selectable_now=True,
                    error=None,
                )
            ],
            reload_skills=lambda: (),
        ),
    )

    async def scenario() -> None:
        skills = await list_ai_skills(_auth_session())
        assert skills[0].name == "skill-alpha"
        assert skills[0].required_tools == ["tool_a"]
        reloaded = await reload_ai_skills(_auth_session())
        assert reloaded[0].name == "skill-alpha"

    asyncio.run(scenario())


def test_ai_tools_routes_list_catalog_and_recent_executions(
    monkeypatch: "MonkeyPatch",
) -> None:
    from apeiria.webui.routes.ai.tools import (
        ai_application,
        list_ai_tools,
        list_recent_ai_tool_executions,
    )

    async def _recent_executions(*, limit: int):
        del limit
        return [
            SimpleNamespace(
                execution_id="tool_obs_1",
                session_id="scene-1",
                tool_name="tool.alpha",
                status="success",
                reason=None,
                trace_id="trace-1",
                call_id="call-1",
                input_json='{"x":1}',
                output_json='{"ok":true}',
                created_at=SimpleNamespace(
                    isoformat=lambda: "2026-05-27T00:00:00+00:00"
                ),
            )
        ]

    monkeypatch.setattr(
        ai_application._operations,
        "_entry",
        SimpleNamespace(
            list_tools=lambda **_kwargs: [
                SimpleNamespace(
                    name="tool.alpha",
                    description="Alpha tool",
                    origin="builtin",
                    required_level=SimpleNamespace(value="read"),
                    enabled=True,
                    manageable=False,
                    readiness=SimpleNamespace(code="ready", reason="ok"),
                    version=1,
                )
            ],
            list_recent_tool_executions=_recent_executions,
        ),
    )

    async def scenario() -> None:
        tools = await list_ai_tools(_auth_session())
        assert tools[0].name == "tool.alpha"
        recent = await list_recent_ai_tool_executions(_auth_session(), limit=10)
        assert recent[0].execution_id == "tool_obs_1"

    asyncio.run(scenario())

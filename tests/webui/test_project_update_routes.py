from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from apeiria.access.principal import AuthSession, Principal, PrincipalRole
from apeiria.access.principal_roles import CAP_CONTROL_PANEL

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404


def test_project_update_status_reads_control_plane() -> None:
    from apeiria.runtime.context import set_current_runtime
    from apeiria.webui.routes.project_update import get_project_update_status

    state = _status_state()
    runtime = SimpleNamespace(
        control_plane=SimpleNamespace(get_project_update_status=lambda: state)
    )
    set_current_runtime(runtime)

    async def scenario() -> None:
        response = await get_project_update_status(_owner_session())
        assert response.checkout.branch == "main"
        assert response.branch.target_ref == "origin/main"

    import asyncio

    try:
        asyncio.run(scenario())
    finally:
        set_current_runtime(None)


def test_project_update_plan_preview_returns_blockers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apeiria.app.system.project_update import (
        ProjectUpdateMessage,
        ProjectUpdatePlan,
    )
    from apeiria.webui.routes import project_update
    from apeiria.webui.schemas.project_update import ProjectUpdatePlanRequest

    monkeypatch.setattr(
        project_update.project_update_service,
        "create_plan",
        lambda _payload: ProjectUpdatePlan(
            channel="branch",
            operation="update",
            target_ref=None,
            target_commit=None,
            blockers=(
                ProjectUpdateMessage(
                    code="missing_upstream",
                    message="Current branch has no upstream.",
                ),
            ),
            confirmation="update",
        ),
    )

    async def scenario() -> None:
        response = await project_update.preview_project_update_plan(
            ProjectUpdatePlanRequest(channel="branch"),
            _owner_session(),
        )
        assert response.allowed is False
        assert response.blockers[0].code == "missing_upstream"

    import asyncio

    asyncio.run(scenario())


def test_project_update_refresh_fetches_remote_refs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apeiria.webui.routes import project_update

    state = _status_state()
    calls: list[bool] = []

    def fake_refresh_remote_refs(*, force: bool = False) -> object:
        calls.append(force)
        return state

    monkeypatch.setattr(
        project_update.project_update_service,
        "refresh_remote_refs",
        fake_refresh_remote_refs,
    )

    async def scenario() -> None:
        response = await project_update.refresh_project_update_status(
            _owner_session(),
        )
        assert response.checkout.branch == "main"
        assert calls == [True]

    import asyncio

    asyncio.run(scenario())


def test_project_update_task_creation_requires_unblocked_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apeiria.app.system.project_update import ProjectUpdateError
    from apeiria.webui.routes import project_update
    from apeiria.webui.schemas.project_update import ProjectUpdatePlanRequest

    async def fake_create_task(_payload: object) -> object:
        raise ProjectUpdateError("blocked")

    monkeypatch.setattr(
        project_update.project_update_service,
        "create_task",
        fake_create_task,
    )

    async def scenario() -> None:
        with pytest.raises(HTTPException) as exc_info:
            await project_update.create_project_update_task(
                ProjectUpdatePlanRequest(channel="branch"),
                _owner_session(),
            )
        assert exc_info.value.status_code == HTTP_BAD_REQUEST
        assert exc_info.value.detail == "blocked"

    import asyncio

    asyncio.run(scenario())


def test_project_update_task_lookup_returns_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apeiria.webui.routes import project_update

    monkeypatch.setattr(
        project_update.project_update_service,
        "get_task",
        _task,
    )

    async def scenario() -> None:
        response = await project_update.get_project_update_task(
            "task-1",
            _owner_session(),
        )
        assert response.task_id == "task-1"
        assert response.restart_required is True

    import asyncio

    asyncio.run(scenario())


def test_project_update_task_lookup_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apeiria.webui.routes import project_update

    monkeypatch.setattr(
        project_update.project_update_service,
        "get_task",
        lambda _task_id: None,
    )

    async def scenario() -> None:
        with pytest.raises(HTTPException) as exc_info:
            await project_update.get_project_update_task("missing", _owner_session())
        assert exc_info.value.status_code == HTTP_NOT_FOUND

    import asyncio

    asyncio.run(scenario())


def _status_state() -> object:
    return SimpleNamespace(
        project_root="/project",
        checkout=SimpleNamespace(
            project_root="/project",
            is_git=True,
            is_detached=False,
            branch="main",
            current_commit="abc",
            short_commit="abc",
            upstream_ref="origin/main",
            upstream_commit="def",
            ahead=0,
            behind=1,
            dirty=False,
            dirty_entries=(),
            head_tags=(),
            blockers=(),
        ),
        branch=SimpleNamespace(
            available=True,
            target_ref="origin/main",
            target_commit="def",
            blockers=(),
            warnings=(),
        ),
        remote_refresh=SimpleNamespace(
            ttl_seconds=1800,
            stale=False,
            last_checked_at="2026-05-20T00:00:00+00:00",
            last_success_at="2026-05-20T00:00:00+00:00",
            next_check_after="2026-05-20T00:30:00+00:00",
            last_error_at=None,
            last_error=None,
            remotes=("origin",),
        ),
        stable_releases=(),
        prerelease_releases=(),
        active_task=None,
    )


def _task(task_id: str) -> object:
    return SimpleNamespace(
        task_id=task_id,
        title="Update branch",
        status="succeeded",
        logs="done\n",
        error=None,
        result={"restart_required": True},
        created_at=None,
        started_at=None,
        finished_at=None,
        channel="branch",
        operation="update",
        target_ref="origin/main",
        target_commit="def",
        target_tag=None,
        target_version=None,
        current_phase="succeeded",
        current_phase_label="Succeeded",
        progress_percent=100,
        restart_required=True,
        steps=(),
        diagnostics=(),
    )


def _owner_session() -> AuthSession:
    return AuthSession(
        principal=Principal(
            principal_kind="webui_account",
            principal_id="owner",
            display_name="owner",
            role=PrincipalRole(
                role_id="owner",
                capabilities=(CAP_CONTROL_PANEL,),
            ),
        ),
        auth_method="password",
        session_version=1,
        token_subject="owner",
    )

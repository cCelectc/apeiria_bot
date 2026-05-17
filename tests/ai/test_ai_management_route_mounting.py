from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apeiria.access.principal import AuthSession, Principal, PrincipalRole
from apeiria.webui.auth import require_control_panel

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
FUTURE_TASK_ROUTE_DEFAULT_LIMIT = 20


def _control_panel_override() -> object:
    return object()


def _control_panel_session_override() -> AuthSession:
    return AuthSession(
        principal=Principal(
            principal_kind="webui_account",
            principal_id="operator-1",
            display_name="operator",
            role=PrincipalRole(
                role_id="owner",
                capabilities=("control_panel",),
            ),
        ),
        auth_method="bearer_token",
        session_version=1,
        token_subject="operator-1",
    )


def _ensure_nonebot_initialized() -> None:
    import nonebot

    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init()


def test_core_webui_router_mounts_ai_management_routes() -> None:
    _ensure_nonebot_initialized()

    from apeiria.webui.routes.router import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    response = client.get("/api/ai/bootstrap")

    assert response.status_code == HTTP_UNAUTHORIZED


def test_ai_management_routes_retain_authorization_when_ai_plugin_disabled(
    tmp_path: "Path",
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    _ensure_nonebot_initialized()

    from apeiria.db.runtime import database_runtime
    from apeiria.plugins.repository import plugin_catalog_repository
    from apeiria.webui.routes.router import router

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    plugin_catalog_repository._ensure_plugin_record_sync("apeiria.builtin_plugins.ai")
    plugin_catalog_repository._set_plugin_enabled_sync(
        "apeiria.builtin_plugins.ai",
        enabled=False,
    )

    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    response = client.get("/api/ai/runtime-status")

    assert response.status_code == HTTP_UNAUTHORIZED


def test_ai_configuration_routes_remain_available_when_ai_plugin_disabled(
    tmp_path: "Path",
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    _ensure_nonebot_initialized()

    from apeiria.db.runtime import database_runtime
    from apeiria.plugins.repository import plugin_catalog_repository
    from apeiria.webui.routes.router import router

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    plugin_catalog_repository._ensure_plugin_record_sync("apeiria.builtin_plugins.ai")
    plugin_catalog_repository._set_plugin_enabled_sync(
        "apeiria.builtin_plugins.ai",
        enabled=False,
    )

    app = FastAPI()
    app.dependency_overrides[require_control_panel] = _control_panel_override
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    bootstrap = client.get("/api/ai/bootstrap")
    sources = client.get("/api/ai/sources")
    personas = client.get("/api/ai/personas")

    assert bootstrap.status_code == HTTP_OK
    assert bootstrap.json()["source_presets"]
    assert sources.status_code == HTTP_OK
    assert sources.json() == []
    assert personas.status_code == HTTP_OK
    assert personas.json() == []


def test_ai_runtime_status_reports_disabled_plugin_state(
    tmp_path: "Path",
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    _ensure_nonebot_initialized()

    from apeiria.db.runtime import database_runtime
    from apeiria.plugins.repository import plugin_catalog_repository
    from apeiria.webui.routes.router import router

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    plugin_catalog_repository._ensure_plugin_record_sync("apeiria.builtin_plugins.ai")
    plugin_catalog_repository._set_plugin_enabled_sync(
        "apeiria.builtin_plugins.ai",
        enabled=False,
    )

    app = FastAPI()
    app.dependency_overrides[require_control_panel] = _control_panel_override
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    response = client.get("/api/ai/runtime-status")

    assert response.status_code == HTTP_OK
    assert response.json()["configuration_api_available"] is True
    assert response.json()["runtime_plugin_module"] == "apeiria.builtin_plugins.ai"
    assert response.json()["runtime_plugin_enabled"] is False
    assert response.json()["runtime_plugin_loaded"] is False


def test_future_task_management_routes_remain_available_when_ai_plugin_disabled(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    _ensure_nonebot_initialized()

    from apeiria.webui.routes.ai import future_tasks as future_task_routes
    from apeiria.webui.routes.router import router

    class FakeFutureTasksEntry:
        async def list_tasks(self, *, limit: int, session_id: str | None = None):
            assert limit == FUTURE_TASK_ROUTE_DEFAULT_LIMIT
            assert session_id is None
            return []

    monkeypatch.setattr(
        future_task_routes,
        "ai_application",
        type("App", (), {"future_tasks": FakeFutureTasksEntry()})(),
    )

    app = FastAPI()
    app.dependency_overrides[require_control_panel] = _control_panel_override
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    response = client.get("/api/ai/future-tasks")

    assert response.status_code == HTTP_OK
    assert response.json() == []


def test_future_task_cancellation_remains_available_when_ai_plugin_disabled(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    _ensure_nonebot_initialized()

    from apeiria.webui.routes.ai import future_tasks as future_task_routes
    from apeiria.webui.routes.router import router

    task = _future_task_definition()

    class FakeFutureTasksEntry:
        def __init__(self) -> None:
            self.cancel_actor: str | None = None

        async def cancel_task(
            self,
            *,
            task_id: str,
            actor_username: str | None = None,
        ):
            assert task_id == "task-1"
            self.cancel_actor = actor_username
            return task

    entry = FakeFutureTasksEntry()
    monkeypatch.setattr(
        future_task_routes,
        "ai_application",
        type("App", (), {"future_tasks": entry})(),
    )

    app = FastAPI()
    app.dependency_overrides[require_control_panel] = _control_panel_session_override
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    response = client.delete("/api/ai/future-tasks", params={"task_id": "task-1"})

    assert response.status_code == HTTP_OK
    assert response.json()["task_id"] == "task-1"
    assert response.json()["status"] == "cancelled"
    assert entry.cancel_actor == "operator"


def _future_task_definition() -> object:
    from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition

    now = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)
    return AIFutureTaskDefinition(
        task_id="task-1",
        session_id="session-1",
        platform="test",
        scene_type="private",
        scene_id="scene-1",
        user_id="user-1",
        title="Wake",
        description="send a reminder",
        trigger_at=now,
        status="cancelled",
        source_message_id="message-1",
        scheduler_job_id="job-1",
        last_error=None,
        created_at=now,
        updated_at=now,
    )

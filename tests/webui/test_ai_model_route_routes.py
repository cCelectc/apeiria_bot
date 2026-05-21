from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from apeiria.access.principal import AuthSession, Principal, PrincipalRole
from apeiria.access.principal_roles import CAP_CONTROL_PANEL
from apeiria.ai.model.catalog.storage import create_source_model
from apeiria.db.runtime import database_runtime
from apeiria.utils.project_context import (
    reset_active_project_root,
    set_active_project_root,
)

_UPDATED_MEMBER_WEIGHT = 2

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_ai_model_route_routes_manage_routes_members_bindings_and_audit(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    token = set_active_project_root(tmp_path)
    try:
        database_runtime.ensure_ready()
        _seed_chat_profile("profile-primary", model_id="model-primary")
        _seed_chat_profile("profile-fallback", model_id="model-fallback")

        from apeiria.app.access.webui_auth import audit as audit_module
        from apeiria.app.access.webui_auth.secrets import list_security_audit_events
        from apeiria.webui.routes.ai.models import (
            delete_ai_model_route_binding,
            list_ai_model_route_bindings,
            list_ai_model_route_members,
            list_ai_model_routes,
            upsert_ai_model_route,
            upsert_ai_model_route_binding,
            upsert_ai_model_route_member,
        )
        from apeiria.webui.routes.ai.models_schemas import (
            AIModelRouteBindingUpsertRequest,
            AIModelRouteMemberUpsertRequest,
            AIModelRouteUpsertRequest,
        )

        monkeypatch.setattr(audit_module, "_mirror_to_governance_audit", _noop_mirror)

        async def scenario() -> None:
            session = _control_panel_session()
            route = await upsert_ai_model_route(
                AIModelRouteUpsertRequest(
                    name="Default reply route",
                    task_class="reply_default",
                    mode="primary_fallback",
                    algorithm="ordered",
                    fallback_on_failure=True,
                    enabled=True,
                ),
                session,
            )
            assert route is not None
            assert route.mode == "primary_fallback"

            updated = await upsert_ai_model_route(
                AIModelRouteUpsertRequest(
                    route_id=route.route_id,
                    name="Reply pool",
                    task_class="reply_default",
                    mode="load_balance",
                    algorithm="weighted_random",
                    fallback_on_failure=False,
                    enabled=True,
                ),
                session,
            )
            assert updated is not None
            assert updated.algorithm == "weighted_random"
            assert updated.fallback_on_failure is False

            first_member = await upsert_ai_model_route_member(
                AIModelRouteMemberUpsertRequest(
                    route_id=route.route_id,
                    profile_id="profile-primary",
                    position=0,
                    weight=5,
                    enabled=True,
                ),
                session,
            )
            second_member = await upsert_ai_model_route_member(
                AIModelRouteMemberUpsertRequest(
                    route_id=route.route_id,
                    profile_id="profile-fallback",
                    position=1,
                    weight=1,
                    enabled=True,
                ),
                session,
            )
            assert first_member is not None
            assert second_member is not None

            toggled_member = await upsert_ai_model_route_member(
                AIModelRouteMemberUpsertRequest(
                    route_member_id=second_member.route_member_id,
                    route_id=route.route_id,
                    profile_id="profile-fallback",
                    position=1,
                    weight=_UPDATED_MEMBER_WEIGHT,
                    enabled=False,
                ),
                session,
            )
            assert toggled_member is not None
            assert toggled_member.weight == _UPDATED_MEMBER_WEIGHT
            assert toggled_member.enabled is False

            binding = await upsert_ai_model_route_binding(
                AIModelRouteBindingUpsertRequest(
                    scope_type="global",
                    scope_id="__global__",
                    task_class="reply_default",
                    route_id=route.route_id,
                ),
                session,
            )
            assert binding.route_id == route.route_id

            routes = await list_ai_model_routes(session)
            members = await list_ai_model_route_members(
                session,
                route_id=route.route_id,
            )
            bindings = await list_ai_model_route_bindings(session)

            assert [item.route_id for item in routes] == [route.route_id]
            assert [item.profile_id for item in members] == [
                "profile-primary",
                "profile-fallback",
            ]
            assert [(item.scope_type, item.task_class) for item in bindings] == [
                ("global", "reply_default")
            ]

            assert await delete_ai_model_route_binding(
                session,
                scope_type="global",
                scope_id="__global__",
                task_class="reply_default",
            )
            assert await list_ai_model_route_bindings(session) == []

        asyncio.run(scenario())

        event_types = [item.event_type for item in list_security_audit_events(limit=10)]
        assert "ai_model_route_created" in event_types
        assert "ai_model_route_updated" in event_types
        assert "ai_model_route_member_created" in event_types
        assert "ai_model_route_member_updated" in event_types
        assert "ai_model_route_binding_updated" in event_types
        assert "ai_model_route_binding_deleted" in event_types
    finally:
        reset_active_project_root(token)


def _seed_chat_profile(profile_id: str, *, model_id: str) -> None:
    with database_runtime.connect_sync() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO ai_source (
                source_id,
                name,
                capability_type,
                client_type,
                preset_type,
                enabled,
                custom_headers_json,
                extra_config_json,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "source-1",
                "Primary",
                "chat_completion",
                "openai",
                "openai_compatible",
                1,
                "{}",
                "{}",
                "2026-05-21T00:00:00",
            ),
        )
    create_source_model(
        "ai_chat_model",
        model_id=model_id,
        source_id="source-1",
        model_identifier=model_id,
        display_name=model_id,
        enabled=True,
        is_default=False,
        extra_params={},
    )
    with database_runtime.connect_sync() as connection:
        connection.execute(
            """
            INSERT INTO ai_model_profile (
                profile_id,
                name,
                model_id,
                task_class,
                priority,
                enabled,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                profile_id,
                model_id,
                "reply_default",
                10,
                1,
                "2026-05-21T00:00:00",
            ),
        )


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


def _noop_mirror(*_args: object, **_kwargs: object) -> None:
    return None

"""Model route CRUD and attempt-plan service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from apeiria.ai.model.routing.bindings import (
    AIModelBindingTarget,
    resolve_model_route_binding,
)
from apeiria.ai.model.routing.models import (
    AIModelRouteAlgorithm,
    AIModelRouteBindingSpec,
    AIModelRouteDefinition,
    AIModelRouteMemberDefinition,
    AIModelRouteMode,
    AIModelRouteQuery,
    AIModelRouteScopeType,
    AIModelTaskClass,
)
from apeiria.ai.model.routing.selection import (
    AIModelAttemptPlan,
    resolve_model_route_attempt_plan,
)
from apeiria.ai.model.sources.service import ai_source_service
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from random import Random


@dataclass(frozen=True)
class AIModelRouteCreateInput:
    """Create or update payload for one model route."""

    name: str
    task_class: AIModelTaskClass
    mode: AIModelRouteMode
    algorithm: AIModelRouteAlgorithm
    fallback_on_failure: bool = True
    enabled: bool = True


@dataclass(frozen=True)
class AIModelRouteMemberCreateInput:
    """Create or update payload for one model route member."""

    route_id: str
    profile_id: str
    position: int
    weight: int = 1
    enabled: bool = True


@dataclass(frozen=True)
class AIModelRouteBindingCreateInput:
    """Create or update payload for one model route binding."""

    scope_type: AIModelRouteScopeType
    scope_id: str
    task_class: AIModelTaskClass
    route_id: str


class AIModelRouteService:
    """Model route persistence and attempt-plan service."""

    async def list_routes(self) -> list[AIModelRouteDefinition]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT
                    route_id,
                    name,
                    task_class,
                    mode,
                    algorithm,
                    fallback_on_failure,
                    enabled
                FROM ai_model_route
                ORDER BY task_class ASC, name ASC, route_id ASC
                """
            ).fetchall()
        return [_row_to_route(row) for row in rows]

    async def create_route(
        self,
        create_input: AIModelRouteCreateInput,
    ) -> AIModelRouteDefinition:
        route = AIModelRouteDefinition(
            route_id=f"route_{uuid4().hex}",
            name=create_input.name,
            task_class=create_input.task_class,
            mode=create_input.mode,
            algorithm=create_input.algorithm,
            fallback_on_failure=create_input.fallback_on_failure,
            enabled=create_input.enabled,
        )
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                INSERT INTO ai_model_route (
                    route_id,
                    name,
                    task_class,
                    mode,
                    algorithm,
                    fallback_on_failure,
                    enabled,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    route.route_id,
                    route.name,
                    route.task_class,
                    route.mode,
                    route.algorithm,
                    1 if route.fallback_on_failure else 0,
                    1 if route.enabled else 0,
                    _utcnow_text(),
                ),
            )
        return route

    async def update_route(
        self,
        *,
        route_id: str,
        create_input: AIModelRouteCreateInput,
    ) -> AIModelRouteDefinition | None:
        updated = AIModelRouteDefinition(
            route_id=route_id,
            name=create_input.name,
            task_class=create_input.task_class,
            mode=create_input.mode,
            algorithm=create_input.algorithm,
            fallback_on_failure=create_input.fallback_on_failure,
            enabled=create_input.enabled,
        )
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                """
                UPDATE ai_model_route
                SET
                    name = ?,
                    task_class = ?,
                    mode = ?,
                    algorithm = ?,
                    fallback_on_failure = ?,
                    enabled = ?,
                    updated_at = ?
                WHERE route_id = ?
                """,
                (
                    updated.name,
                    updated.task_class,
                    updated.mode,
                    updated.algorithm,
                    1 if updated.fallback_on_failure else 0,
                    1 if updated.enabled else 0,
                    _utcnow_text(),
                    route_id,
                ),
            )
        return updated if cursor.rowcount > 0 else None

    async def delete_route(self, *, route_id: str) -> bool:
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                "DELETE FROM ai_model_route WHERE route_id = ?",
                (route_id,),
            )
        return cursor.rowcount > 0

    async def list_members(
        self,
        *,
        route_id: str | None = None,
    ) -> list[AIModelRouteMemberDefinition]:
        where = "WHERE route_id = ?" if route_id else ""
        params = (route_id,) if route_id else ()
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    route_member_id,
                    route_id,
                    profile_id,
                    position,
                    weight,
                    enabled
                FROM ai_model_route_member
                {where}
                ORDER BY route_id ASC, position ASC, route_member_id ASC
                """,
                params,
            ).fetchall()
        return [_row_to_member(row) for row in rows]

    async def create_member(
        self,
        create_input: AIModelRouteMemberCreateInput,
    ) -> AIModelRouteMemberDefinition:
        member = AIModelRouteMemberDefinition(
            route_member_id=f"route_member_{uuid4().hex}",
            route_id=create_input.route_id,
            profile_id=create_input.profile_id,
            position=create_input.position,
            weight=create_input.weight,
            enabled=create_input.enabled,
        )
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                INSERT INTO ai_model_route_member (
                    route_member_id,
                    route_id,
                    profile_id,
                    position,
                    weight,
                    enabled,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    member.route_member_id,
                    member.route_id,
                    member.profile_id,
                    member.position,
                    member.weight,
                    1 if member.enabled else 0,
                    _utcnow_text(),
                ),
            )
        return member

    async def update_member(
        self,
        *,
        route_member_id: str,
        create_input: AIModelRouteMemberCreateInput,
    ) -> AIModelRouteMemberDefinition | None:
        updated = AIModelRouteMemberDefinition(
            route_member_id=route_member_id,
            route_id=create_input.route_id,
            profile_id=create_input.profile_id,
            position=create_input.position,
            weight=create_input.weight,
            enabled=create_input.enabled,
        )
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                """
                UPDATE ai_model_route_member
                SET
                    route_id = ?,
                    profile_id = ?,
                    position = ?,
                    weight = ?,
                    enabled = ?,
                    updated_at = ?
                WHERE route_member_id = ?
                """,
                (
                    updated.route_id,
                    updated.profile_id,
                    updated.position,
                    updated.weight,
                    1 if updated.enabled else 0,
                    _utcnow_text(),
                    route_member_id,
                ),
            )
        return updated if cursor.rowcount > 0 else None

    async def delete_member(self, *, route_member_id: str) -> bool:
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                "DELETE FROM ai_model_route_member WHERE route_member_id = ?",
                (route_member_id,),
            )
        return cursor.rowcount > 0

    async def list_bindings(self) -> list[AIModelRouteBindingSpec]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT binding_id, scope_type, scope_id, task_class, route_id
                FROM ai_model_route_binding
                ORDER BY binding_id ASC
                """
            ).fetchall()
        return [_row_to_binding(row) for row in rows]

    async def upsert_binding(
        self,
        create_input: AIModelRouteBindingCreateInput,
    ) -> AIModelRouteBindingSpec:
        binding_id = (
            "route_binding_"
            f"{create_input.scope_type}_{create_input.scope_id}_"
            f"{create_input.task_class}"
        )
        binding = AIModelRouteBindingSpec(
            binding_id=binding_id,
            scope_type=create_input.scope_type,
            scope_id=create_input.scope_id,
            task_class=create_input.task_class,
            route_id=create_input.route_id,
        )
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                INSERT INTO ai_model_route_binding (
                    binding_id,
                    scope_type,
                    scope_id,
                    task_class,
                    route_id,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope_type, scope_id, task_class)
                DO UPDATE SET
                    route_id = excluded.route_id,
                    updated_at = excluded.updated_at
                """,
                (
                    binding.binding_id,
                    binding.scope_type,
                    binding.scope_id,
                    binding.task_class,
                    binding.route_id,
                    _utcnow_text(),
                ),
            )
        return binding

    async def delete_binding(
        self,
        *,
        scope_type: str,
        scope_id: str,
        task_class: AIModelTaskClass,
    ) -> bool:
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                """
                DELETE FROM ai_model_route_binding
                WHERE scope_type = ? AND scope_id = ? AND task_class = ?
                """,
                (scope_type, scope_id, task_class),
            )
        return cursor.rowcount > 0

    async def resolve_attempt_plan(
        self,
        query: AIModelRouteQuery,
        *,
        target: AIModelBindingTarget | None = None,
        randomizer: "Random | None" = None,
    ) -> AIModelAttemptPlan | None:
        from apeiria.ai.model.catalog.chat import ai_chat_model_service
        from apeiria.ai.model.routing.profile import ai_model_profile_service

        routes = await self.list_routes()
        route = None
        if target is not None:
            binding = resolve_model_route_binding(
                await self.list_bindings(),
                target,
                task_class=query.task_class,
            )
            if binding is not None:
                route = _route_by_id(routes, binding.route_id)
        if route is None:
            route = _default_route_for_task(routes, query.task_class)
        if route is not None:
            members = await self.list_members(route_id=route.route_id)
            profiles = await ai_model_profile_service.list_profiles()
            sources = await ai_source_service.list_sources()
            source_models = await ai_chat_model_service.list_all_models()
            plan = resolve_model_route_attempt_plan(
                route,
                members,
                profiles,
                sources,
                source_models,
                randomizer=randomizer,
            )
            if plan is not None:
                return plan

        fallback_selected = await ai_model_profile_service.select_model(
            query=query,
            target=target,
        )
        if fallback_selected is not None:
            return AIModelAttemptPlan(route=None, selected=fallback_selected)
        return None


def _row_to_route(row: tuple[object, ...]) -> AIModelRouteDefinition:
    return AIModelRouteDefinition(
        route_id=str(row[0]),
        name=str(row[1]),
        task_class=cast("AIModelTaskClass", str(row[2])),
        mode=cast("AIModelRouteMode", str(row[3])),
        algorithm=cast("AIModelRouteAlgorithm", str(row[4])),
        fallback_on_failure=bool(row[5]),
        enabled=bool(row[6]),
    )


def _row_to_member(row: tuple[object, ...]) -> AIModelRouteMemberDefinition:
    return AIModelRouteMemberDefinition(
        route_member_id=str(row[0]),
        route_id=str(row[1]),
        profile_id=str(row[2]),
        position=_row_int(row[3]),
        weight=_row_int(row[4]),
        enabled=bool(row[5]),
    )


def _row_to_binding(row: tuple[object, ...]) -> AIModelRouteBindingSpec:
    return AIModelRouteBindingSpec(
        binding_id=str(row[0]),
        scope_type=cast("AIModelRouteScopeType", str(row[1])),
        scope_id=str(row[2]),
        task_class=cast("AIModelTaskClass", str(row[3])),
        route_id=str(row[4]),
    )


def _row_int(value: object) -> int:
    return int(cast("int | str", value))


def _route_by_id(
    routes: list[AIModelRouteDefinition],
    route_id: str,
) -> AIModelRouteDefinition | None:
    return next(
        (route for route in routes if route.route_id == route_id and route.enabled),
        None,
    )


def _default_route_for_task(
    routes: list[AIModelRouteDefinition],
    task_class: AIModelTaskClass,
) -> AIModelRouteDefinition | None:
    candidates = [
        route for route in routes if route.enabled and route.task_class == task_class
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item.name, item.route_id))[0]


def _utcnow_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


ai_model_route_service = AIModelRouteService()

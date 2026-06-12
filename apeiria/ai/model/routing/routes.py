"""Model route CRUD and attempt-plan service."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert

from apeiria.ai.model.catalog.chat import AIChatModelService
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
from apeiria.ai.model.routing.profile import AIModelProfileService
from apeiria.ai.model.routing.selection import (
    AIModelAttemptPlan,
    resolve_model_route_attempt_plan,
    selected_model_diagnostics,
)
from apeiria.ai.model.sources.service import AISourceService
from apeiria.db.base import _epoch_ms
from apeiria.db.engine import get_session, rowcount
from apeiria.db.models.ai_routing import (
    AIModelRoute,
    AIModelRouteBinding,
    AIModelRouteMember,
)

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

    def __init__(
        self,
        *,
        source_service: AISourceService | None = None,
        chat_model_service: AIChatModelService | None = None,
        profile_service: AIModelProfileService | None = None,
    ) -> None:
        self._source_service = source_service or AISourceService()
        self._chat_model_service = chat_model_service or AIChatModelService()
        self._profile_service = profile_service or AIModelProfileService(
            source_service=self._source_service,
            chat_model_service=self._chat_model_service,
        )

    async def list_routes(self) -> list[AIModelRouteDefinition]:
        async with get_session() as session:
            result = await session.execute(
                select(AIModelRoute).order_by(
                    AIModelRoute.task_class.asc(),
                    AIModelRoute.name.asc(),
                    AIModelRoute.route_id.asc(),
                )
            )
            rows = result.scalars().all()
        return [_orm_to_route(row) for row in rows]

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
        now = _epoch_ms()
        async with get_session() as session:
            instance = AIModelRoute(
                route_id=route.route_id,
                name=route.name,
                task_class=route.task_class,
                mode=route.mode,
                algorithm=route.algorithm,
                fallback_on_failure=1 if route.fallback_on_failure else 0,
                enabled=1 if route.enabled else 0,
                updated_at=now,
            )
            session.add(instance)
            await session.commit()
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
        async with get_session() as session:
            row = await session.get(AIModelRoute, route_id)
            if row is None:
                return None
            row.name = updated.name
            row.task_class = updated.task_class
            row.mode = updated.mode
            row.algorithm = updated.algorithm
            row.fallback_on_failure = 1 if updated.fallback_on_failure else 0
            row.enabled = 1 if updated.enabled else 0
            row.updated_at = _epoch_ms()
            await session.commit()
        return updated

    async def delete_route(self, *, route_id: str) -> bool:
        async with get_session() as session:
            result = await session.execute(
                delete(AIModelRoute).where(AIModelRoute.route_id == route_id)
            )
            await session.commit()
        return rowcount(result) > 0

    async def list_members(
        self,
        *,
        route_id: str | None = None,
    ) -> list[AIModelRouteMemberDefinition]:
        stmt = select(AIModelRouteMember)
        if route_id:
            stmt = stmt.where(AIModelRouteMember.route_id == route_id)
        stmt = stmt.order_by(
            AIModelRouteMember.route_id.asc(),
            AIModelRouteMember.position.asc(),
            AIModelRouteMember.route_member_id.asc(),
        )
        async with get_session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [_orm_to_member(row) for row in rows]

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
        now = _epoch_ms()
        async with get_session() as session:
            instance = AIModelRouteMember(
                route_member_id=member.route_member_id,
                route_id=member.route_id,
                profile_id=member.profile_id,
                position=member.position,
                weight=member.weight,
                enabled=1 if member.enabled else 0,
                updated_at=now,
            )
            session.add(instance)
            await session.commit()
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
        async with get_session() as session:
            row = await session.get(AIModelRouteMember, route_member_id)
            if row is None:
                return None
            row.route_id = updated.route_id
            row.profile_id = updated.profile_id
            row.position = updated.position
            row.weight = updated.weight
            row.enabled = 1 if updated.enabled else 0
            row.updated_at = _epoch_ms()
            await session.commit()
        return updated

    async def delete_member(self, *, route_member_id: str) -> bool:
        async with get_session() as session:
            result = await session.execute(
                delete(AIModelRouteMember).where(
                    AIModelRouteMember.route_member_id == route_member_id
                )
            )
            await session.commit()
        return rowcount(result) > 0

    async def list_bindings(self) -> list[AIModelRouteBindingSpec]:
        async with get_session() as session:
            result = await session.execute(
                select(AIModelRouteBinding).order_by(
                    AIModelRouteBinding.binding_id.asc()
                )
            )
            rows = result.scalars().all()
        return [_orm_to_binding(row) for row in rows]

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
        now = _epoch_ms()
        async with get_session() as session:
            stmt = insert(AIModelRouteBinding).values(
                binding_id=binding.binding_id,
                scope_type=binding.scope_type,
                scope_id=binding.scope_id,
                task_class=binding.task_class,
                route_id=binding.route_id,
                updated_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["scope_type", "scope_id", "task_class"],
                set_={
                    "route_id": stmt.excluded.route_id,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            await session.execute(stmt)
            await session.commit()
        return binding

    async def delete_binding(
        self,
        *,
        scope_type: str,
        scope_id: str,
        task_class: AIModelTaskClass,
    ) -> bool:
        async with get_session() as session:
            result = await session.execute(
                delete(AIModelRouteBinding).where(
                    AIModelRouteBinding.scope_type == scope_type,
                    AIModelRouteBinding.scope_id == scope_id,
                    AIModelRouteBinding.task_class == task_class,
                )
            )
            await session.commit()
        return rowcount(result) > 0

    async def resolve_attempt_plan(
        self,
        query: AIModelRouteQuery,
        *,
        target: AIModelBindingTarget | None = None,
        randomizer: "Random | None" = None,
    ) -> AIModelAttemptPlan | None:
        routes = await self.list_routes()
        matched_binding = None
        route = None
        if target is not None:
            binding = resolve_model_route_binding(
                await self.list_bindings(),
                target,
                task_class=query.task_class,
            )
            if binding is not None:
                route = _route_by_id(routes, binding.route_id)
                if route is not None:
                    matched_binding = binding
        if route is None:
            route = _default_route_for_task(routes, query.task_class)
        if route is not None:
            members = await self.list_members(route_id=route.route_id)
            profiles = await self._profile_service.list_profiles()
            sources = await self._source_service.list_sources()
            source_models = await self._chat_model_service.list_all_models()
            plan = resolve_model_route_attempt_plan(
                route,
                members,
                profiles,
                sources,
                source_models,
                randomizer=randomizer,
            )
            if plan is not None:
                return replace(
                    plan,
                    routing_diagnostics=_route_source_diagnostics(
                        plan,
                        binding=matched_binding,
                    ),
                )

        fallback_selected = await self._profile_service.select_model(
            query=query,
            target=target,
        )
        if fallback_selected is not None:
            return AIModelAttemptPlan(
                route=None,
                selected=fallback_selected,
                routing_diagnostics={
                    "source": "profile_fallback",
                    **selected_model_diagnostics(fallback_selected),
                    "fallback_model_count": 0,
                },
            )
        return None


def _orm_to_route(row: AIModelRoute) -> AIModelRouteDefinition:
    return AIModelRouteDefinition(
        route_id=str(row.route_id),
        name=str(row.name),
        task_class=cast("AIModelTaskClass", str(row.task_class)),
        mode=cast("AIModelRouteMode", str(row.mode)),
        algorithm=cast("AIModelRouteAlgorithm", str(row.algorithm)),
        fallback_on_failure=bool(row.fallback_on_failure),
        enabled=bool(row.enabled),
    )


def _orm_to_member(row: AIModelRouteMember) -> AIModelRouteMemberDefinition:
    return AIModelRouteMemberDefinition(
        route_member_id=str(row.route_member_id),
        route_id=str(row.route_id),
        profile_id=str(row.profile_id),
        position=int(row.position),
        weight=int(row.weight),
        enabled=bool(row.enabled),
    )


def _orm_to_binding(row: AIModelRouteBinding) -> AIModelRouteBindingSpec:
    return AIModelRouteBindingSpec(
        binding_id=str(row.binding_id),
        scope_type=cast("AIModelRouteScopeType", str(row.scope_type)),
        scope_id=str(row.scope_id),
        task_class=cast("AIModelTaskClass", str(row.task_class)),
        route_id=str(row.route_id),
    )


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


def _route_source_diagnostics(
    plan: AIModelAttemptPlan,
    *,
    binding: AIModelRouteBindingSpec | None,
) -> dict[str, object]:
    diagnostics = dict(plan.routing_diagnostics)
    if binding is None:
        diagnostics["source"] = "default_route"
        return diagnostics
    diagnostics.update(
        {
            "source": "route",
            "binding_id": binding.binding_id,
            "binding_scope_type": binding.scope_type,
            "binding_scope_id": binding.scope_id,
        }
    )
    return diagnostics

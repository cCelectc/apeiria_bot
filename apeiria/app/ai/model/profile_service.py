"""Model profile CRUD and routing service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from sqlalchemy import select

from apeiria.app.ai.model.bindings import (
    AIModelBindingSpec,
    AIModelBindingTarget,
    resolve_model_binding,
)
from apeiria.app.ai.model.chat_model_service import ai_chat_model_service
from apeiria.app.ai.model.models import (
    AIModelProfileDefinition,
    AIModelRouteQuery,
    AIModelTaskClass,
)
from apeiria.app.ai.model.routing import (
    list_model_profile_candidates,
    resolve_model_profile,
)
from apeiria.app.ai.model.selection import (
    AISelectedModel,
    resolve_source_selected_model_with_fallback,
)
from apeiria.app.ai.model.source_service import ai_source_service
from apeiria.infra.db.models import AIModelBinding, AIModelProfile

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AIModelProfileCreateInput:
    """Create payload for one model routing profile."""

    name: str
    model_id: str
    task_class: AIModelTaskClass
    priority: int
    enabled: bool = True
    fallback_profile_id: str | None = None


class AIModelProfileService:
    """Model profile persistence and task routing service."""

    async def list_profiles(
        self,
        session: "AsyncSession",
    ) -> list[AIModelProfileDefinition]:
        result = await session.execute(
            select(AIModelProfile).order_by(
                AIModelProfile.priority.asc(),
                AIModelProfile.id.asc(),
            )
        )
        return [
            AIModelProfileDefinition(
                profile_id=row.profile_id,
                name=row.name,
                model_id=row.model_id or "",
                task_class=cast("AIModelTaskClass", row.task_class),
                priority=row.priority,
                enabled=row.enabled,
                fallback_profile_id=row.fallback_profile_id,
            )
            for row in result.scalars().all()
        ]

    async def list_bindings(
        self,
        session: "AsyncSession",
    ) -> list[AIModelBindingSpec]:
        result = await session.execute(
            select(AIModelBinding).order_by(AIModelBinding.id.asc())
        )
        return [
            AIModelBindingSpec(
                binding_id=row.binding_id,
                scope_type=row.scope_type,
                scope_id=row.scope_id,
                profile_id=row.profile_id,
            )
            for row in result.scalars().all()
        ]

    async def create_profile(
        self,
        session: "AsyncSession",
        create_input: AIModelProfileCreateInput,
    ) -> AIModelProfile:
        row = AIModelProfile(
            profile_id=f"profile_{uuid4().hex}",
            name=create_input.name,
            model_id=create_input.model_id,
            task_class=create_input.task_class,
            priority=create_input.priority,
            enabled=create_input.enabled,
            fallback_profile_id=create_input.fallback_profile_id,
        )
        session.add(row)
        await session.flush()
        return row

    async def update_profile(
        self,
        session: "AsyncSession",
        *,
        profile_id: str,
        create_input: AIModelProfileCreateInput,
    ) -> AIModelProfile | None:
        result = await session.execute(
            select(AIModelProfile).where(AIModelProfile.profile_id == profile_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.name = create_input.name
        row.model_id = create_input.model_id
        row.task_class = create_input.task_class
        row.priority = create_input.priority
        row.enabled = create_input.enabled
        row.fallback_profile_id = create_input.fallback_profile_id
        await session.flush()
        return row

    async def resolve_profile(
        self,
        session: "AsyncSession",
        query: AIModelRouteQuery,
    ) -> AIModelProfileDefinition | None:
        profiles = await self.list_profiles(session)
        return resolve_model_profile(profiles, query)

    async def resolve_profile_for_target(
        self,
        session: "AsyncSession",
        *,
        target: AIModelBindingTarget,
    ) -> AIModelProfileDefinition | None:
        profiles = await self.list_profiles(session)
        bindings = await self.list_bindings(session)
        binding = resolve_model_binding(bindings, target)
        if binding is None:
            return None
        profile_map = {
            profile.profile_id: profile for profile in profiles if profile.enabled
        }
        return profile_map.get(binding.profile_id)

    async def select_model(
        self,
        session: "AsyncSession",
        query: AIModelRouteQuery | None = None,
        *,
        target: AIModelBindingTarget | None = None,
    ) -> AISelectedModel | None:
        profiles = await self.list_profiles(session)
        candidate_profiles: list[AIModelProfileDefinition] = []
        if target is not None:
            bound_profile = await self.resolve_profile_for_target(
                session,
                target=target,
            )
            if bound_profile is not None:
                candidate_profiles.append(bound_profile)
        if query is not None:
            candidate_profiles.extend(list_model_profile_candidates(profiles, query))
        deduped_candidates = list(
            {profile.profile_id: profile for profile in candidate_profiles}.values()
        )
        if not deduped_candidates:
            return None
        sources = await ai_source_service.list_sources(session)
        source_models = await ai_chat_model_service.list_all_models(session)
        return resolve_source_selected_model_with_fallback(
            sources,
            source_models,
            profiles,
            deduped_candidates,
        )


ai_model_profile_service = AIModelProfileService()

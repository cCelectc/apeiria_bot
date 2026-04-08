"""Model profile CRUD and routing service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from sqlalchemy import select

from apeiria.app.ai.models.bindings import (
    AIModelBindingSpec,
    AIModelBindingTarget,
    resolve_model_binding,
)
from apeiria.app.ai.models.models import (
    AIModelProfileDefinition,
    AIModelRouteQuery,
    AIModelTaskClass,
)
from apeiria.app.ai.models.routing import resolve_model_profile
from apeiria.app.ai.models.selection import (
    AISelectedModel,
    select_provider_for_profile,
)
from apeiria.app.ai.providers.service import ai_provider_service
from apeiria.infra.db.models import AIModelBinding, AIModelProfile

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AIModelProfileCreateInput:
    """Create payload for one model routing profile."""

    name: str
    provider_id: str
    model_name: str
    task_class: AIModelTaskClass
    priority: int
    enabled: bool = True
    fallback_profile_id: str | None = None


class AIModelService:
    """Model profile persistence and task routing service."""

    async def list_profiles(
        self,
        session: AsyncSession,
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
                provider_id=row.provider_id,
                model_name=row.model_name,
                task_class=cast("AIModelTaskClass", row.task_class),
                priority=row.priority,
                enabled=row.enabled,
                fallback_profile_id=row.fallback_profile_id,
            )
            for row in result.scalars().all()
        ]

    async def list_bindings(
        self,
        session: AsyncSession,
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
        session: AsyncSession,
        create_input: AIModelProfileCreateInput,
    ) -> AIModelProfile:
        row = AIModelProfile(
            profile_id=f"profile_{uuid4().hex}",
            name=create_input.name,
            provider_id=create_input.provider_id,
            model_name=create_input.model_name,
            task_class=create_input.task_class,
            priority=create_input.priority,
            enabled=create_input.enabled,
            fallback_profile_id=create_input.fallback_profile_id,
        )
        session.add(row)
        await session.flush()
        return row

    async def resolve_profile(
        self,
        session: AsyncSession,
        query: AIModelRouteQuery,
    ) -> AIModelProfileDefinition | None:
        profiles = await self.list_profiles(session)
        return resolve_model_profile(profiles, query)

    async def resolve_profile_for_target(
        self,
        session: AsyncSession,
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
        session: AsyncSession,
        query: AIModelRouteQuery | None = None,
        *,
        target: AIModelBindingTarget | None = None,
    ) -> AISelectedModel | None:
        """Resolve the effective provider + profile pair for one task class."""

        profile = None
        if target is not None:
            profile = await self.resolve_profile_for_target(session, target=target)
        if profile is None:
            if query is None:
                return None
            profile = await self.resolve_profile(session, query)
        if profile is None:
            return None
        providers = await ai_provider_service.list_providers(session)
        provider = select_provider_for_profile(providers, profile)
        if provider is None:
            return None
        return AISelectedModel(provider=provider, profile=profile)


ai_model_service = AIModelService()

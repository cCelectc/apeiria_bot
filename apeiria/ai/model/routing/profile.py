"""Model profile CRUD and routing service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import uuid4

from sqlalchemy import select

from apeiria.ai.model.catalog.chat import AIChatModelService
from apeiria.ai.model.routing.bindings import (
    AIModelBindingSpec,
    AIModelBindingTarget,
    resolve_model_binding,
)
from apeiria.ai.model.routing.models import (
    AIModelProfileDefinition,
    AIModelRouteQuery,
    AIModelTaskClass,
)
from apeiria.ai.model.routing.rules import (
    list_model_profile_candidates,
    resolve_model_profile,
)
from apeiria.ai.model.routing.selection import (
    AISelectedModel,
    resolve_implicit_selected_model,
    resolve_source_selected_model_with_fallback,
)
from apeiria.ai.model.sources.service import AISourceService
from apeiria.db.base import _epoch_ms
from apeiria.db.engine import get_session
from apeiria.db.models.ai_routing import AIModelBinding, AIModelProfile


@dataclass(frozen=True)
class AIModelProfileCreateInput:
    """Create payload for one model routing profile."""

    name: str
    model_id: str
    task_class: AIModelTaskClass
    priority: int
    enabled: bool = True


class AIModelProfileService:
    """Model profile persistence and task routing service."""

    def __init__(
        self,
        *,
        source_service: AISourceService | None = None,
        chat_model_service: AIChatModelService | None = None,
    ) -> None:
        self._source_service = source_service or AISourceService()
        self._chat_model_service = chat_model_service or AIChatModelService()

    async def list_profiles(
        self,
    ) -> list[AIModelProfileDefinition]:
        async with get_session() as session:
            result = await session.execute(
                select(AIModelProfile).order_by(
                    AIModelProfile.priority.asc(),
                    AIModelProfile.profile_id.asc(),
                )
            )
            rows = result.scalars().all()
        return [
            AIModelProfileDefinition(
                profile_id=str(row.profile_id),
                name=str(row.name),
                model_id=str(row.model_id),
                task_class=cast("AIModelTaskClass", str(row.task_class)),
                priority=int(row.priority),
                enabled=bool(row.enabled),
                fallback_profile_id=(
                    str(row.fallback_profile_id)
                    if row.fallback_profile_id is not None
                    else None
                ),
            )
            for row in rows
        ]

    async def list_bindings(
        self,
    ) -> list[AIModelBindingSpec]:
        async with get_session() as session:
            result = await session.execute(
                select(AIModelBinding).order_by(AIModelBinding.binding_id.asc())
            )
            rows = result.scalars().all()
        return [
            AIModelBindingSpec(
                binding_id=str(row.binding_id),
                scope_type=str(row.scope_type),
                scope_id=str(row.scope_id),
                profile_id=str(row.profile_id),
            )
            for row in rows
        ]

    async def create_profile(
        self,
        create_input: AIModelProfileCreateInput,
    ) -> AIModelProfileDefinition:
        profile = AIModelProfileDefinition(
            profile_id=f"profile_{uuid4().hex}",
            name=create_input.name,
            model_id=create_input.model_id,
            task_class=create_input.task_class,
            priority=create_input.priority,
            enabled=create_input.enabled,
            fallback_profile_id=None,
        )
        now = _epoch_ms()
        async with get_session() as session:
            instance = AIModelProfile(
                profile_id=profile.profile_id,
                name=profile.name,
                model_id=profile.model_id,
                task_class=profile.task_class,
                priority=profile.priority,
                enabled=1 if profile.enabled else 0,
                fallback_profile_id=profile.fallback_profile_id,
                updated_at=now,
            )
            session.add(instance)
            await session.commit()
        return profile

    async def update_profile(
        self,
        *,
        profile_id: str,
        create_input: AIModelProfileCreateInput,
    ) -> AIModelProfileDefinition | None:
        existing = next(
            (
                item
                for item in await self.list_profiles()
                if item.profile_id == profile_id
            ),
            None,
        )
        if existing is None:
            return None
        updated = AIModelProfileDefinition(
            profile_id=profile_id,
            name=create_input.name,
            model_id=create_input.model_id,
            task_class=create_input.task_class,
            priority=create_input.priority,
            enabled=create_input.enabled,
            fallback_profile_id=None,
        )
        async with get_session() as session:
            row = await session.get(AIModelProfile, profile_id)
            if row is None:
                return None
            row.name = updated.name
            row.model_id = updated.model_id
            row.task_class = updated.task_class
            row.priority = updated.priority
            row.enabled = 1 if updated.enabled else 0
            row.fallback_profile_id = updated.fallback_profile_id
            row.updated_at = _epoch_ms()
            await session.commit()
        return updated

    async def resolve_profile(
        self,
        query: AIModelRouteQuery,
    ) -> AIModelProfileDefinition | None:
        profiles = await self.list_profiles()
        return resolve_model_profile(profiles, query)

    async def resolve_profile_for_target(
        self,
        *,
        target: AIModelBindingTarget,
    ) -> AIModelProfileDefinition | None:
        profiles = await self.list_profiles()
        bindings = await self.list_bindings()
        binding = resolve_model_binding(bindings, target)
        if binding is None:
            return None
        profile_map = {
            profile.profile_id: profile for profile in profiles if profile.enabled
        }
        return profile_map.get(binding.profile_id)

    async def select_model(
        self,
        query: AIModelRouteQuery | None = None,
        *,
        target: AIModelBindingTarget | None = None,
    ) -> AISelectedModel | None:
        profiles = await self.list_profiles()
        candidate_profiles: list[AIModelProfileDefinition] = []
        if target is not None:
            bound_profile = await self.resolve_profile_for_target(
                target=target,
            )
            if bound_profile is not None:
                candidate_profiles.append(bound_profile)
        if query is not None:
            candidate_profiles.extend(list_model_profile_candidates(profiles, query))
        sources = await self._source_service.list_sources()
        source_models = await self._chat_model_service.list_all_models()
        deduped_candidates = list(
            {profile.profile_id: profile for profile in candidate_profiles}.values()
        )
        if deduped_candidates:
            selected = resolve_source_selected_model_with_fallback(
                sources,
                source_models,
                profiles,
                deduped_candidates,
            )
            if selected is not None:
                return selected
        return resolve_implicit_selected_model(
            sources,
            source_models,
            query=query,
        )

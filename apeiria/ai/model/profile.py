"""Model profile CRUD and routing service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import cast
from uuid import uuid4

from apeiria.ai.model.bindings import (
    AIModelBindingSpec,
    AIModelBindingTarget,
    resolve_model_binding,
)
from apeiria.ai.model.models import (
    AIModelProfileDefinition,
    AIModelRouteQuery,
    AIModelTaskClass,
)
from apeiria.ai.model.routing import (
    list_model_profile_candidates,
    resolve_model_profile,
)
from apeiria.ai.model.selection import (
    AISelectedModel,
    resolve_implicit_selected_model,
    resolve_source_selected_model_with_fallback,
)
from apeiria.ai.model.source import ai_source_service
from apeiria.db.runtime import database_runtime


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
    ) -> list[AIModelProfileDefinition]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT
                    profile_id,
                    name,
                    model_id,
                    task_class,
                    priority,
                    enabled,
                    fallback_profile_id
                FROM ai_model_profile
                ORDER BY priority ASC, profile_id ASC
                """
            ).fetchall()
        return [
            AIModelProfileDefinition(
                profile_id=str(row[0]),
                name=str(row[1]),
                model_id=str(row[2]),
                task_class=cast("AIModelTaskClass", str(row[3])),
                priority=int(row[4]),
                enabled=bool(row[5]),
                fallback_profile_id=(str(row[6]) if row[6] is not None else None),
            )
            for row in rows
        ]

    async def list_bindings(
        self,
    ) -> list[AIModelBindingSpec]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT binding_id, scope_type, scope_id, profile_id
                FROM ai_model_binding
                ORDER BY binding_id ASC
                """
            ).fetchall()
        return [
            AIModelBindingSpec(
                binding_id=str(row[0]),
                scope_type=str(row[1]),
                scope_id=str(row[2]),
                profile_id=str(row[3]),
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
            fallback_profile_id=create_input.fallback_profile_id,
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
                    fallback_profile_id,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.profile_id,
                    profile.name,
                    profile.model_id,
                    profile.task_class,
                    profile.priority,
                    1 if profile.enabled else 0,
                    profile.fallback_profile_id,
                    _utcnow_text(),
                ),
            )
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
            fallback_profile_id=create_input.fallback_profile_id,
        )
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE ai_model_profile
                SET
                    name = ?,
                    model_id = ?,
                    task_class = ?,
                    priority = ?,
                    enabled = ?,
                    fallback_profile_id = ?,
                    updated_at = ?
                WHERE profile_id = ?
                """,
                (
                    updated.name,
                    updated.model_id,
                    updated.task_class,
                    updated.priority,
                    1 if updated.enabled else 0,
                    updated.fallback_profile_id,
                    _utcnow_text(),
                    profile_id,
                ),
            )
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
        from apeiria.ai.model.chat_model import ai_chat_model_service

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
        sources = await ai_source_service.list_sources()
        source_models = await ai_chat_model_service.list_all_models()
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


ai_model_profile_service = AIModelProfileService()


def _utcnow_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

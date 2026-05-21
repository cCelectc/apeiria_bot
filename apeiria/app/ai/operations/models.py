"""Model / source-model / profile / binding admin operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from apeiria.ai.model import (
    AIModelProfileCreateInput,
    AIModelRouteBindingCreateInput,
    AIModelRouteCreateInput,
    AIModelRouteMemberCreateInput,
    AISourceCapabilityType,
    ai_chat_model_service,
    ai_embedding_model_service,
    ai_model_profile_service,
    ai_model_route_service,
    ai_rerank_model_service,
    ai_source_service,
    ai_stt_model_service,
    ai_tts_model_service,
)
from apeiria.ai.model.catalog.capability_templates import enrich_model_capabilities
from apeiria.ai.model.runtime.capability_sources import (
    capability_provenance_to_metadata,
)
from apeiria.app.ai.diagnostics.audit import record_ai_admin_audit
from apeiria.app.ai.operations.errors import (
    AIAdminModelNotFoundError,
    AISourceModelDeleteBlockedError,
)

if TYPE_CHECKING:
    from apeiria.ai.model import (
        AIModelBindingSpec,
        AIModelCatalogItem,
        AIModelProfileDefinition,
        AIModelRouteBindingSpec,
        AIModelRouteDefinition,
        AIModelRouteMemberDefinition,
        AIModelRouteScopeType,
        AISourceDefinition,
        AISourceModelDefinition,
    )
    from apeiria.ai.model.catalog.registry import (
        AICapabilityModelRegistryEntry,
    )


def _get_source_model_capability_fallback_order() -> tuple[
    "AISourceCapabilityType", ...
]:
    from apeiria.ai.model.catalog.registry import (
        SOURCE_MODEL_CAPABILITY_FALLBACK_ORDER,
    )

    return SOURCE_MODEL_CAPABILITY_FALLBACK_ORDER


class ModelsAdminMixin:
    """Admin CRUD and test hooks for model profiles, bindings, and source models."""

    async def list_model_profiles(self) -> list["AIModelProfileDefinition"]:
        return await ai_model_profile_service.list_profiles()

    async def create_model_profile(  # noqa: PLR0913
        self,
        *,
        name: str,
        model_id: str,
        task_class: str,
        priority: int,
        enabled: bool,
        actor_username: str | None = None,
    ) -> "AIModelProfileDefinition":
        create_input = await self._build_profile_create_input(
            name=name,
            model_id=model_id,
            task_class=task_class,
            priority=priority,
            enabled=enabled,
        )
        created = await ai_model_profile_service.create_profile(create_input)
        record_ai_admin_audit(
            "ai_model_profile_created",
            actor_username=actor_username,
            detail=f"{created.profile_id} {created.name}",
        )
        return created

    async def update_model_profile(  # noqa: PLR0913
        self,
        *,
        profile_id: str,
        name: str,
        model_id: str,
        task_class: str,
        priority: int,
        enabled: bool,
        actor_username: str | None = None,
    ) -> "AIModelProfileDefinition | None":
        create_input = await self._build_profile_create_input(
            name=name,
            model_id=model_id,
            task_class=task_class,
            priority=priority,
            enabled=enabled,
        )
        updated = await ai_model_profile_service.update_profile(
            profile_id=profile_id,
            create_input=create_input,
        )
        if updated is not None:
            record_ai_admin_audit(
                "ai_model_profile_updated",
                actor_username=actor_username,
                detail=f"{updated.profile_id} {updated.name}",
            )
        return updated

    async def list_model_bindings(self) -> list["AIModelBindingSpec"]:
        return await ai_model_profile_service.list_bindings()

    async def list_model_routes(self) -> list["AIModelRouteDefinition"]:
        return await ai_model_route_service.list_routes()

    async def create_model_route(  # noqa: PLR0913
        self,
        *,
        name: str,
        task_class: str,
        mode: str,
        algorithm: str,
        fallback_on_failure: bool,
        enabled: bool,
        actor_username: str | None = None,
    ) -> "AIModelRouteDefinition":
        route = await ai_model_route_service.create_route(
            AIModelRouteCreateInput(
                name=name,
                task_class=task_class,  # type: ignore[arg-type]
                mode=mode,  # type: ignore[arg-type]
                algorithm=algorithm,  # type: ignore[arg-type]
                fallback_on_failure=fallback_on_failure,
                enabled=enabled,
            )
        )
        record_ai_admin_audit(
            "ai_model_route_created",
            actor_username=actor_username,
            detail=f"{route.route_id} {route.name}",
        )
        return route

    async def update_model_route(  # noqa: PLR0913
        self,
        *,
        route_id: str,
        name: str,
        task_class: str,
        mode: str,
        algorithm: str,
        fallback_on_failure: bool,
        enabled: bool,
        actor_username: str | None = None,
    ) -> "AIModelRouteDefinition | None":
        route = await ai_model_route_service.update_route(
            route_id=route_id,
            create_input=AIModelRouteCreateInput(
                name=name,
                task_class=task_class,  # type: ignore[arg-type]
                mode=mode,  # type: ignore[arg-type]
                algorithm=algorithm,  # type: ignore[arg-type]
                fallback_on_failure=fallback_on_failure,
                enabled=enabled,
            ),
        )
        if route is not None:
            record_ai_admin_audit(
                "ai_model_route_updated",
                actor_username=actor_username,
                detail=f"{route.route_id} {route.name}",
            )
        return route

    async def delete_model_route(
        self,
        *,
        route_id: str,
        actor_username: str | None = None,
    ) -> bool:
        deleted = await ai_model_route_service.delete_route(route_id=route_id)
        if deleted:
            record_ai_admin_audit(
                "ai_model_route_deleted",
                actor_username=actor_username,
                detail=route_id,
            )
        return deleted

    async def list_model_route_members(
        self,
        *,
        route_id: str | None = None,
    ) -> list["AIModelRouteMemberDefinition"]:
        return await ai_model_route_service.list_members(route_id=route_id)

    async def create_model_route_member(  # noqa: PLR0913
        self,
        *,
        route_id: str,
        profile_id: str,
        position: int,
        weight: int,
        enabled: bool,
        actor_username: str | None = None,
    ) -> "AIModelRouteMemberDefinition":
        member = await ai_model_route_service.create_member(
            AIModelRouteMemberCreateInput(
                route_id=route_id,
                profile_id=profile_id,
                position=position,
                weight=weight,
                enabled=enabled,
            )
        )
        record_ai_admin_audit(
            "ai_model_route_member_created",
            actor_username=actor_username,
            detail=f"{member.route_id} {member.profile_id}",
        )
        return member

    async def update_model_route_member(  # noqa: PLR0913
        self,
        *,
        route_member_id: str,
        route_id: str,
        profile_id: str,
        position: int,
        weight: int,
        enabled: bool,
        actor_username: str | None = None,
    ) -> "AIModelRouteMemberDefinition | None":
        member = await ai_model_route_service.update_member(
            route_member_id=route_member_id,
            create_input=AIModelRouteMemberCreateInput(
                route_id=route_id,
                profile_id=profile_id,
                position=position,
                weight=weight,
                enabled=enabled,
            ),
        )
        if member is not None:
            record_ai_admin_audit(
                "ai_model_route_member_updated",
                actor_username=actor_username,
                detail=f"{member.route_id} {member.profile_id}",
            )
        return member

    async def delete_model_route_member(
        self,
        *,
        route_member_id: str,
        actor_username: str | None = None,
    ) -> bool:
        deleted = await ai_model_route_service.delete_member(
            route_member_id=route_member_id
        )
        if deleted:
            record_ai_admin_audit(
                "ai_model_route_member_deleted",
                actor_username=actor_username,
                detail=route_member_id,
            )
        return deleted

    async def list_model_route_bindings(self) -> list["AIModelRouteBindingSpec"]:
        return await ai_model_route_service.list_bindings()

    async def upsert_model_route_binding(
        self,
        *,
        scope_type: str,
        scope_id: str,
        task_class: str,
        route_id: str,
        actor_username: str | None = None,
    ) -> "AIModelRouteBindingSpec":
        binding = await ai_model_route_service.upsert_binding(
            AIModelRouteBindingCreateInput(
                scope_type=cast("AIModelRouteScopeType", scope_type),
                scope_id=scope_id,
                task_class=task_class,  # type: ignore[arg-type]
                route_id=route_id,
            )
        )
        record_ai_admin_audit(
            "ai_model_route_binding_updated",
            actor_username=actor_username,
            detail=f"{binding.scope_type}:{binding.scope_id} {binding.task_class}",
        )
        return binding

    async def delete_model_route_binding(
        self,
        *,
        scope_type: str,
        scope_id: str,
        task_class: str,
        actor_username: str | None = None,
    ) -> bool:
        deleted = await ai_model_route_service.delete_binding(
            scope_type=scope_type,
            scope_id=scope_id,
            task_class=task_class,  # type: ignore[arg-type]
        )
        if deleted:
            record_ai_admin_audit(
                "ai_model_route_binding_deleted",
                actor_username=actor_username,
                detail=f"{scope_type}:{scope_id} {task_class}",
            )
        return deleted

    async def list_source_models(
        self,
        *,
        source_id: str,
    ) -> list["AISourceModelDefinition"]:
        source = await ai_source_service.get_source(source_id=source_id)
        if source is None:
            return []
        return await self._list_managed_models(
            source=source,
            source_id=source_id,
        )

    async def fetch_source_models(
        self,
        *,
        source_id: str | None = None,
        preset_type: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        extra_config: dict[str, object] | None = None,
    ) -> list["AIModelCatalogItem"]:
        from apeiria.app.ai.diagnostics.model_connectivity import (
            fetch_source_model_catalog,
        )

        return await fetch_source_model_catalog(
            source_id=source_id,
            preset_type=preset_type,
            api_base=api_base,
            api_key=api_key,
            extra_config=extra_config,
        )

    async def create_source_model(  # noqa: PLR0913
        self,
        *,
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        capability_metadata: dict[str, object] | None = None,
        default_options: dict[str, object] | None = None,
        capability_provenance: dict[str, object] | None = None,
        actor_username: str | None = None,
    ) -> "AISourceModelDefinition":
        source = await ai_source_service.get_source(source_id=source_id)
        if source is None:
            raise AIAdminModelNotFoundError
        created = await self._create_managed_model(
            source=source,
            source_id=source_id,
            model_identifier=model_identifier,
            display_name=display_name,
            enabled=enabled,
            is_default=is_default,
            extra_params=extra_params,
            capability_metadata=capability_metadata,
            default_options=default_options,
            capability_provenance=capability_provenance,
        )
        record_ai_admin_audit(
            "ai_source_model_created",
            actor_username=actor_username,
            detail=f"{created.model_id} {created.display_name}",
        )
        return created

    async def update_source_model(  # noqa: PLR0913
        self,
        *,
        model_id: str,
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        capability_metadata: dict[str, object] | None = None,
        default_options: dict[str, object] | None = None,
        capability_provenance: dict[str, object] | None = None,
        actor_username: str | None = None,
    ) -> "AISourceModelDefinition | None":
        source = await ai_source_service.get_source(source_id=source_id)
        if source is None:
            return None
        updated = await self._update_managed_model(
            source=source,
            model_id=model_id,
            source_id=source_id,
            model_identifier=model_identifier,
            display_name=display_name,
            enabled=enabled,
            is_default=is_default,
            extra_params=extra_params,
            capability_metadata=capability_metadata,
            default_options=default_options,
            capability_provenance=capability_provenance,
        )
        if updated is not None:
            record_ai_admin_audit(
                "ai_source_model_updated",
                actor_username=actor_username,
                detail=f"{updated.model_id} {updated.display_name}",
            )
        return updated

    async def delete_source_model(
        self,
        *,
        model_id: str,
        source_id: str | None = None,
        actor_username: str | None = None,
    ) -> bool:
        capability_type = await self._resolve_model_capability_type(
            model_id=model_id,
            source_id=source_id,
        )
        existing_label = await self._build_source_model_audit_label(
            capability_type=capability_type,
            model_id=model_id,
        )
        dependent_profiles = await self._list_dependent_chat_model_profiles(
            capability_type=capability_type,
            model_id=model_id,
        )
        if dependent_profiles:
            labels = tuple(profile.name for profile in dependent_profiles[:3])
            raise AISourceModelDeleteBlockedError(
                profile_count=len(dependent_profiles),
                profile_labels=labels,
            )
        deleted = False
        if source_id:
            source = await ai_source_service.get_source(source_id=source_id)
            if source is not None:
                deleted = await self._delete_managed_model(
                    capability_type=source.capability_type,
                    model_id=model_id,
                )
            else:
                deleted = await self._delete_managed_model(
                    capability_type="chat_completion",
                    model_id=model_id,
                )
        if not deleted:
            for capability_type in _get_source_model_capability_fallback_order():
                deleted = await self._delete_managed_model(
                    capability_type=capability_type,
                    model_id=model_id,
                )
                if deleted:
                    break
        if deleted:
            record_ai_admin_audit(
                "ai_source_model_deleted",
                actor_username=actor_username,
                detail=existing_label,
            )
        return deleted

    async def _build_source_model_audit_label(
        self,
        *,
        capability_type: "AISourceCapabilityType | None",
        model_id: str,
    ) -> str:
        if capability_type != "chat_completion":
            return model_id
        existing = await ai_chat_model_service.get_model(model_id=model_id)
        if existing is None:
            return model_id
        return f"{existing.model_id} {existing.display_name}"

    async def _list_dependent_chat_model_profiles(
        self,
        *,
        capability_type: "AISourceCapabilityType | None",
        model_id: str,
    ) -> list["AIModelProfileDefinition"]:
        if capability_type != "chat_completion":
            return []
        profiles = await ai_model_profile_service.list_profiles()
        return [profile for profile in profiles if profile.model_id == model_id]

    async def test_source_model(  # noqa: PLR0913
        self,
        *,
        source_id: str | None = None,
        preset_type: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        extra_config: dict[str, object] | None = None,
        model_identifier: str,
    ) -> tuple[str, str, int]:
        from apeiria.app.ai.diagnostics.model_connectivity import (
            test_source_model_connectivity,
        )

        return await test_source_model_connectivity(
            source_id=source_id,
            preset_type=preset_type,
            api_base=api_base,
            api_key=api_key,
            extra_config=extra_config,
            model_identifier=model_identifier,
        )

    async def _build_profile_create_input(
        self,
        *,
        name: str,
        model_id: str,
        task_class: str,
        priority: int,
        enabled: bool,
    ) -> AIModelProfileCreateInput:
        if not model_id.strip():
            raise AIAdminModelNotFoundError
        return AIModelProfileCreateInput(
            name=name,
            model_id=model_id,
            task_class=task_class,  # type: ignore[arg-type]
            priority=priority,
            enabled=enabled,
        )

    async def _create_managed_model(  # noqa: PLR0913
        self,
        *,
        source: "AISourceDefinition",
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        capability_metadata: dict[str, object] | None,
        default_options: dict[str, object] | None,
        capability_provenance: dict[str, object] | None,
    ) -> "AISourceModelDefinition":
        entry = self._get_model_capability_entry(source.capability_type)
        enrichment = enrich_model_capabilities(
            source=source,
            model_identifier=model_identifier,
            owner_capability_metadata=capability_metadata or None,
            owner_default_options=default_options or None,
            existing_provenance=capability_provenance,
        )
        return await entry.create_model(
            source_id,
            model_identifier,
            display_name,
            enabled,
            is_default,
            extra_params,
            enrichment.capability_metadata,
            enrichment.default_options,
            capability_provenance_to_metadata(enrichment.provenance),
        )

    async def _update_managed_model(  # noqa: PLR0913
        self,
        *,
        source: "AISourceDefinition",
        model_id: str,
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        capability_metadata: dict[str, object] | None,
        default_options: dict[str, object] | None,
        capability_provenance: dict[str, object] | None,
    ) -> "AISourceModelDefinition | None":
        entry = self._get_model_capability_entry(source.capability_type)
        existing = await entry.get_model(model_id)
        enrichment = enrich_model_capabilities(
            source=source,
            model_identifier=model_identifier,
            owner_capability_metadata=capability_metadata or None,
            owner_default_options=default_options or None,
            existing_provenance=(
                capability_provenance
                or (existing.capability_provenance if existing else None)
            ),
        )
        return await entry.update_model(
            model_id,
            source_id,
            model_identifier,
            display_name,
            enabled,
            is_default,
            extra_params,
            enrichment.capability_metadata,
            enrichment.default_options,
            capability_provenance_to_metadata(enrichment.provenance),
        )

    async def _list_managed_models(
        self,
        *,
        source: "AISourceDefinition",
        source_id: str,
    ) -> list["AISourceModelDefinition"]:
        entry = self._get_model_capability_entry(source.capability_type)
        return await entry.list_models(
            source_id,
        )

    async def _delete_managed_model(
        self,
        *,
        capability_type: "AISourceCapabilityType",
        model_id: str,
    ) -> bool:
        entry = self._get_model_capability_entry(capability_type)
        return await entry.delete_model(model_id)

    async def _resolve_model_capability_type(
        self,
        *,
        model_id: str,
        source_id: str | None = None,
    ) -> "AISourceCapabilityType | None":
        if source_id:
            source = await ai_source_service.get_source(source_id=source_id)
            if source is not None:
                return source.capability_type

        lookups = (
            (
                cast("AISourceCapabilityType", "chat_completion"),
                ai_chat_model_service.get_model,
            ),
            (
                cast("AISourceCapabilityType", "embedding"),
                ai_embedding_model_service.get_model,
            ),
            (
                cast("AISourceCapabilityType", "speech_to_text"),
                ai_stt_model_service.get_model,
            ),
            (
                cast("AISourceCapabilityType", "text_to_speech"),
                ai_tts_model_service.get_model,
            ),
            (
                cast("AISourceCapabilityType", "rerank"),
                ai_rerank_model_service.get_model,
            ),
        )
        for capability_type, get_model in lookups:
            if await get_model(model_id=model_id) is not None:
                return cast("AISourceCapabilityType", capability_type)
        return None

    @staticmethod
    def _get_model_capability_entry(
        capability_type: "AISourceCapabilityType",
    ) -> "AICapabilityModelRegistryEntry":
        from apeiria.ai.model.catalog.registry import (
            SOURCE_MODEL_CAPABILITY_REGISTRY,
        )

        return SOURCE_MODEL_CAPABILITY_REGISTRY[capability_type]


__all__ = ["ModelsAdminMixin"]

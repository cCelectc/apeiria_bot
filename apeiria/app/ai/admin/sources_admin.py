"""Source admin operations (CRUD over AI model sources)."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from nonebot_plugin_orm import get_session

from apeiria.app.ai.admin.audit import record_ai_admin_audit
from apeiria.app.ai.admin.errors import AISourceDeleteBlockedError
from apeiria.app.ai.model.source_service import AISourceCreateInput, ai_source_service
from apeiria.app.ai.model.sources import (
    AISourcePresetType,
    UnsupportedAISourcePresetError,
    resolve_client_type_for_preset,
)

if TYPE_CHECKING:
    from apeiria.app.ai.model import (
        AISourceDefinition,
        AISourcePresetDefinition,
    )


def coerce_source_preset_type(
    preset_type: str,
) -> AISourcePresetType:
    """Reject unknown preset types; used by source and source-model CRUD."""

    known_preset_types = {item.preset_type for item in ai_source_service.list_presets()}
    if preset_type in known_preset_types:
        return cast("AISourcePresetType", preset_type)
    raise UnsupportedAISourcePresetError


class SourcesAdminMixin:
    """Admin CRUD for AI source connectors."""

    def list_source_presets(self) -> tuple["AISourcePresetDefinition", ...]:
        return ai_source_service.list_presets()

    async def list_sources(self) -> list["AISourceDefinition"]:
        async with get_session() as session:
            return await ai_source_service.list_sources(session)

    async def create_source(  # noqa: PLR0913
        self,
        *,
        name: str,
        capability_type: str,
        preset_type: str,
        api_base: str | None,
        api_key_env_name: str | None,
        enabled: bool,
        timeout_seconds: int | None,
        custom_headers: dict[str, str],
        extra_config: dict[str, object],
        actor_username: str | None = None,
    ) -> "AISourceDefinition":
        async with get_session() as session:
            await ai_source_service.create_source(
                session,
                AISourceCreateInput(
                    name=name,
                    capability_type=capability_type,  # type: ignore[arg-type]
                    client_type=resolve_client_type_for_preset(
                        coerce_source_preset_type(preset_type)
                    ),
                    preset_type=coerce_source_preset_type(preset_type),
                    api_base=api_base,
                    api_key_env_name=api_key_env_name,
                    enabled=enabled,
                    timeout_seconds=timeout_seconds,
                    custom_headers=custom_headers,
                    extra_config=extra_config,
                ),
            )
            await session.commit()
            created = (await ai_source_service.list_sources(session))[-1]
            record_ai_admin_audit(
                "ai_source_created",
                actor_username=actor_username,
                detail=f"{created.source_id} {created.name}",
            )
            return created

    async def update_source(  # noqa: PLR0913
        self,
        *,
        source_id: str,
        name: str,
        capability_type: str,
        preset_type: str,
        api_base: str | None,
        api_key_env_name: str | None,
        enabled: bool,
        timeout_seconds: int | None,
        custom_headers: dict[str, str],
        extra_config: dict[str, object],
        actor_username: str | None = None,
    ) -> "AISourceDefinition | None":
        async with get_session() as session:
            row = await ai_source_service.update_source(
                session,
                source_id=source_id,
                create_input=AISourceCreateInput(
                    name=name,
                    capability_type=capability_type,  # type: ignore[arg-type]
                    client_type=resolve_client_type_for_preset(
                        coerce_source_preset_type(preset_type)
                    ),
                    preset_type=coerce_source_preset_type(preset_type),
                    api_base=api_base,
                    api_key_env_name=api_key_env_name,
                    enabled=enabled,
                    timeout_seconds=timeout_seconds,
                    custom_headers=custom_headers,
                    extra_config=extra_config,
                ),
            )
            if row is None:
                return None
            await session.commit()
            sources = await ai_source_service.list_sources(session)
            updated = next(
                (item for item in sources if item.source_id == source_id),
                None,
            )
            if updated is not None:
                record_ai_admin_audit(
                    "ai_source_updated",
                    actor_username=actor_username,
                    detail=f"{updated.source_id} {updated.name}",
                )
            return updated

    async def delete_source(
        self,
        *,
        source_id: str,
        actor_username: str | None = None,
    ) -> bool:
        async with get_session() as session:
            source = await ai_source_service.get_source(session, source_id=source_id)
            dependency_report = await ai_source_service.build_delete_dependency_report(
                session,
                source_id=source_id,
            )
            if dependency_report is not None:
                raise AISourceDeleteBlockedError(
                    model_count=dependency_report.model_count,
                    model_labels=dependency_report.model_labels,
                )
            deleted = await ai_source_service.delete_source(
                session,
                source_id=source_id,
            )
            if deleted:
                await session.commit()
                record_ai_admin_audit(
                    "ai_source_deleted",
                    actor_username=actor_username,
                    detail=(
                        f"{source.source_id} {source.name}"
                        if source is not None
                        else source_id
                    ),
                )
            return deleted


__all__ = ["SourcesAdminMixin", "coerce_source_preset_type"]

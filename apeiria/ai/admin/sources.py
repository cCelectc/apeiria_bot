"""Source admin operations (CRUD over AI model sources)."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, cast

from apeiria.ai.admin.audit import record_ai_admin_audit
from apeiria.ai.admin.errors import AISourceDeleteBlockedError
from apeiria.ai.model.source import AISourceCreateInput, ai_source_service
from apeiria.ai.model.sources import (
    AISourcePresetType,
    UnsupportedAISourcePresetError,
    resolve_capability_type_for_preset,
    resolve_client_type_for_preset,
)

if TYPE_CHECKING:
    from apeiria.ai.model import (
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
        return await ai_source_service.list_sources()

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
        _ = capability_type
        coerced_preset_type = coerce_source_preset_type(preset_type)
        created = await ai_source_service.create_source(
            AISourceCreateInput(
                name=name,
                capability_type=resolve_capability_type_for_preset(coerced_preset_type),
                client_type=resolve_client_type_for_preset(coerced_preset_type),
                preset_type=coerced_preset_type,
                api_base=api_base,
                api_key_env_name=api_key_env_name,
                enabled=enabled,
                timeout_seconds=timeout_seconds,
                custom_headers=custom_headers,
                extra_config=extra_config,
            ),
        )
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
        _ = capability_type
        coerced_preset_type = coerce_source_preset_type(preset_type)
        updated = await ai_source_service.update_source(
            source_id=source_id,
            create_input=AISourceCreateInput(
                name=name,
                capability_type=resolve_capability_type_for_preset(coerced_preset_type),
                client_type=resolve_client_type_for_preset(coerced_preset_type),
                preset_type=coerced_preset_type,
                api_base=api_base,
                api_key_env_name=api_key_env_name,
                enabled=enabled,
                timeout_seconds=timeout_seconds,
                custom_headers=custom_headers,
                extra_config=extra_config,
            ),
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
        source = await ai_source_service.get_source(source_id=source_id)
        dependency_report = await ai_source_service.build_delete_dependency_report(
            source_id=source_id,
        )
        if dependency_report is not None:
            raise AISourceDeleteBlockedError(
                model_count=dependency_report.model_count,
                model_labels=dependency_report.model_labels,
            )
        try:
            deleted = await ai_source_service.delete_source(
                source_id=source_id,
            )
        except sqlite3.IntegrityError:
            dependency_report = await ai_source_service.build_delete_dependency_report(
                source_id=source_id,
            )
            raise AISourceDeleteBlockedError(
                model_count=dependency_report.model_count
                if dependency_report is not None
                else 1,
                model_labels=(
                    dependency_report.model_labels
                    if dependency_report is not None
                    else ()
                ),
            ) from None
        if deleted:
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

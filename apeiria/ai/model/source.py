"""Source registry CRUD service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from sqlalchemy import select

from apeiria.ai.model.sources import (
    SOURCE_PRESETS,
    AISourceCapabilityType,
    AISourceClientType,
    AISourceDefinition,
    AISourcePresetDefinition,
    AISourcePresetType,
)
from apeiria.db.models import AISource

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AISourceCreateInput:
    """Create or update payload for one AI source."""

    name: str
    capability_type: AISourceCapabilityType
    client_type: AISourceClientType
    preset_type: AISourcePresetType
    api_base: str | None = None
    api_key_env_name: str | None = None
    enabled: bool = True
    timeout_seconds: int | None = None
    custom_headers: dict[str, str] | None = None
    extra_config: dict[str, Any] | None = None


@dataclass(frozen=True)
class AISourceDeleteDependencyReport:
    """Dependency report returned when deleting one source is unsafe."""

    model_count: int
    model_labels: tuple[str, ...]


class AISourceService:
    """Source registry CRUD service."""

    @staticmethod
    def list_presets() -> tuple[AISourcePresetDefinition, ...]:
        return SOURCE_PRESETS

    async def list_sources(
        self,
        session: "AsyncSession",
    ) -> list[AISourceDefinition]:
        result = await session.execute(
            select(AISource).order_by(AISource.name.asc(), AISource.id.asc())
        )
        return [
            AISourceDefinition(
                source_id=row.source_id,
                name=row.name,
                capability_type=cast("AISourceCapabilityType", row.capability_type),
                client_type=cast("AISourceClientType", row.client_type),
                preset_type=cast("AISourcePresetType", row.preset_type),
                api_base=row.api_base,
                api_key_env_name=row.api_key_env_name,
                enabled=row.enabled,
                timeout_seconds=row.timeout_seconds,
                custom_headers=row.custom_headers_json or {},
                extra_config=row.extra_config_json or {},
            )
            for row in result.scalars().all()
        ]

    async def get_source(
        self,
        session: "AsyncSession",
        *,
        source_id: str,
    ) -> AISourceDefinition | None:
        result = await session.execute(
            select(AISource).where(AISource.source_id == source_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return AISourceDefinition(
            source_id=row.source_id,
            name=row.name,
            capability_type=cast("AISourceCapabilityType", row.capability_type),
            client_type=cast("AISourceClientType", row.client_type),
            preset_type=cast("AISourcePresetType", row.preset_type),
            api_base=row.api_base,
            api_key_env_name=row.api_key_env_name,
            enabled=row.enabled,
            timeout_seconds=row.timeout_seconds,
            custom_headers=row.custom_headers_json or {},
            extra_config=row.extra_config_json or {},
        )

    async def create_source(
        self,
        session: "AsyncSession",
        create_input: AISourceCreateInput,
    ) -> AISource:
        row = AISource(
            source_id=f"source_{uuid4().hex}",
            name=create_input.name,
            capability_type=create_input.capability_type,
            client_type=create_input.client_type,
            preset_type=create_input.preset_type,
            api_base=create_input.api_base,
            api_key_env_name=create_input.api_key_env_name,
            enabled=create_input.enabled,
            timeout_seconds=create_input.timeout_seconds,
            custom_headers_json=create_input.custom_headers or {},
            extra_config_json=create_input.extra_config or {},
        )
        session.add(row)
        await session.flush()
        return row

    @staticmethod
    def build_ephemeral_source(  # noqa: PLR0913
        *,
        name: str,
        capability_type: AISourceCapabilityType,
        client_type: AISourceClientType,
        preset_type: AISourcePresetType,
        api_base: str | None,
        api_key_env_name: str | None,
        enabled: bool = True,
        timeout_seconds: int | None = None,
        custom_headers: dict[str, str] | None = None,
        extra_config: dict[str, Any] | None = None,
    ) -> AISourceDefinition:
        return AISourceDefinition(
            source_id="preview_source",
            name=name,
            capability_type=capability_type,
            client_type=client_type,
            preset_type=preset_type,
            api_base=api_base,
            api_key_env_name=api_key_env_name,
            enabled=enabled,
            timeout_seconds=timeout_seconds,
            custom_headers=custom_headers or {},
            extra_config=extra_config or {},
        )

    async def update_source(
        self,
        session: "AsyncSession",
        *,
        source_id: str,
        create_input: AISourceCreateInput,
    ) -> AISource | None:
        result = await session.execute(
            select(AISource).where(AISource.source_id == source_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.name = create_input.name
        row.capability_type = create_input.capability_type
        row.client_type = create_input.client_type
        row.preset_type = create_input.preset_type
        row.api_base = create_input.api_base
        row.api_key_env_name = create_input.api_key_env_name
        row.enabled = create_input.enabled
        row.timeout_seconds = create_input.timeout_seconds
        row.custom_headers_json = create_input.custom_headers or {}
        row.extra_config_json = create_input.extra_config or {}
        await session.flush()
        return row

    async def delete_source(
        self,
        session: "AsyncSession",
        *,
        source_id: str,
    ) -> bool:
        result = await session.execute(
            select(AISource).where(AISource.source_id == source_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await session.delete(row)
        await session.flush()
        return True

    async def build_delete_dependency_report(
        self,
        session: "AsyncSession",
        *,
        source_id: str,
    ) -> AISourceDeleteDependencyReport | None:
        from apeiria.ai.model.capability_registry import (
            SOURCE_MODEL_CAPABILITY_REGISTRY,
        )

        source = await self.get_source(session, source_id=source_id)
        if source is None:
            return None
        entry = SOURCE_MODEL_CAPABILITY_REGISTRY[source.capability_type]
        models = await entry.list_models(session, source_id)
        if not models:
            return None
        labels = tuple(
            item.display_name or item.model_identifier for item in models[:3]
        )
        return AISourceDeleteDependencyReport(
            model_count=len(models),
            model_labels=labels,
        )

    @staticmethod
    def get_source_api_key(source: AISourceDefinition) -> str | None:
        inline_api_key = _extract_inline_api_key(source)
        if inline_api_key:
            return inline_api_key
        if not source.api_key_env_name:
            return None
        value = os.getenv(source.api_key_env_name)
        return value.strip() if isinstance(value, str) and value.strip() else None


ai_source_service = AISourceService()


def _extract_inline_api_key(source: AISourceDefinition) -> str | None:
    extra_config = source.extra_config or {}
    raw_api_keys = extra_config.get("api_keys")
    if not isinstance(raw_api_keys, list):
        return None
    for value in raw_api_keys:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None

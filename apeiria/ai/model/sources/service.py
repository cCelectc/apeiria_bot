"""Source registry CRUD service."""

from __future__ import annotations

from dataclasses import dataclass
from json import dumps
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from sqlalchemy import delete, select

from apeiria.ai.model.sources.models import (
    SOURCE_PRESETS,
    AISourceCapabilityType,
    AISourceClientType,
    AISourceDefinition,
    AISourcePresetDefinition,
    AISourcePresetType,
    resolve_adapter_kind_for_client_type,
)
from apeiria.db.base import _epoch_ms
from apeiria.db.engine import get_session, rowcount
from apeiria.db.models.ai_source import AISource
from apeiria.utils.json_utils import safe_json_loads

if TYPE_CHECKING:
    from apeiria.ai.model.runtime.capabilities import AIModelAdapterKind


@dataclass(frozen=True)
class AISourceCreateInput:
    """Create or update payload for one AI source."""

    name: str
    capability_type: AISourceCapabilityType
    client_type: AISourceClientType
    preset_type: AISourcePresetType
    api_base: str | None = None
    enabled: bool = True
    timeout_seconds: int | None = None
    custom_headers: dict[str, str] | None = None
    extra_config: dict[str, Any] | None = None
    adapter_kind: str | None = None
    capability_metadata: dict[str, Any] | None = None
    default_options: dict[str, Any] | None = None
    capability_provenance: dict[str, Any] | None = None


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

    async def list_sources(self) -> list[AISourceDefinition]:
        async with get_session() as session:
            result = await session.execute(
                select(AISource).order_by(AISource.name.asc(), AISource.source_id.asc())
            )
            rows = result.scalars().all()
        return [self._orm_to_definition(row) for row in rows]

    async def get_source(
        self,
        *,
        source_id: str,
    ) -> AISourceDefinition | None:
        async with get_session() as session:
            row = await session.get(AISource, source_id)
        if row is None:
            return None
        return self._orm_to_definition(row)

    async def create_source(
        self,
        create_input: AISourceCreateInput,
    ) -> AISourceDefinition:
        source = AISourceDefinition(
            source_id=f"source_{uuid4().hex}",
            name=create_input.name,
            capability_type=create_input.capability_type,
            client_type=create_input.client_type,
            preset_type=create_input.preset_type,
            api_base=create_input.api_base,
            enabled=create_input.enabled,
            timeout_seconds=create_input.timeout_seconds,
            custom_headers=create_input.custom_headers or {},
            extra_config=create_input.extra_config or {},
            adapter_kind=cast(
                "AIModelAdapterKind",
                create_input.adapter_kind
                or resolve_adapter_kind_for_client_type(create_input.client_type),
            ),
            capability_metadata=create_input.capability_metadata or {},
            default_options=create_input.default_options or {},
            capability_provenance=create_input.capability_provenance or {},
        )
        now = _epoch_ms()
        async with get_session() as session:
            instance = AISource(
                source_id=source.source_id,
                name=source.name,
                capability_type=source.capability_type,
                client_type=source.client_type,
                preset_type=source.preset_type,
                api_base=source.api_base,
                enabled=1 if source.enabled else 0,
                timeout_seconds=source.timeout_seconds,
                custom_headers_json=dumps(
                    source.custom_headers or {}, ensure_ascii=False
                ),
                extra_config_json=dumps(source.extra_config or {}, ensure_ascii=False),
                adapter_kind=source.adapter_kind,
                capability_metadata_json=dumps(
                    source.capability_metadata or {}, ensure_ascii=False
                ),
                default_options_json=dumps(
                    source.default_options or {}, ensure_ascii=False
                ),
                capability_provenance_json=dumps(
                    source.capability_provenance or {}, ensure_ascii=False
                ),
                updated_at=now,
            )
            session.add(instance)
            await session.commit()
        return source

    @staticmethod
    def build_ephemeral_source(  # noqa: PLR0913
        *,
        name: str,
        capability_type: AISourceCapabilityType,
        client_type: AISourceClientType,
        preset_type: AISourcePresetType,
        api_base: str | None,
        enabled: bool = True,
        timeout_seconds: int | None = None,
        custom_headers: dict[str, str] | None = None,
        extra_config: dict[str, Any] | None = None,
        adapter_kind: str | None = None,
        capability_metadata: dict[str, Any] | None = None,
        default_options: dict[str, Any] | None = None,
        capability_provenance: dict[str, Any] | None = None,
    ) -> AISourceDefinition:
        return AISourceDefinition(
            source_id="preview_source",
            name=name,
            capability_type=capability_type,
            client_type=client_type,
            preset_type=preset_type,
            api_base=api_base,
            enabled=enabled,
            timeout_seconds=timeout_seconds,
            custom_headers=custom_headers or {},
            extra_config=extra_config or {},
            adapter_kind=cast(
                "AIModelAdapterKind",
                adapter_kind or resolve_adapter_kind_for_client_type(client_type),
            ),
            capability_metadata=capability_metadata or {},
            default_options=default_options or {},
            capability_provenance=capability_provenance or {},
        )

    async def update_source(
        self,
        *,
        source_id: str,
        create_input: AISourceCreateInput,
    ) -> AISourceDefinition | None:
        existing = await self.get_source(source_id=source_id)
        if existing is None:
            return None
        updated = AISourceDefinition(
            source_id=source_id,
            name=create_input.name,
            capability_type=create_input.capability_type,
            client_type=create_input.client_type,
            preset_type=create_input.preset_type,
            api_base=create_input.api_base,
            enabled=create_input.enabled,
            timeout_seconds=create_input.timeout_seconds,
            custom_headers=create_input.custom_headers or {},
            extra_config=create_input.extra_config or {},
            adapter_kind=cast(
                "AIModelAdapterKind",
                create_input.adapter_kind
                or resolve_adapter_kind_for_client_type(create_input.client_type),
            ),
            capability_metadata=create_input.capability_metadata or {},
            default_options=create_input.default_options or {},
            capability_provenance=create_input.capability_provenance or {},
        )
        async with get_session() as session:
            row = await session.get(AISource, source_id)
            if row is None:
                return None
            row.name = updated.name
            row.capability_type = updated.capability_type
            row.client_type = updated.client_type
            row.preset_type = updated.preset_type
            row.api_base = updated.api_base
            row.enabled = 1 if updated.enabled else 0
            row.timeout_seconds = updated.timeout_seconds
            row.custom_headers_json = dumps(
                updated.custom_headers or {}, ensure_ascii=False
            )
            row.extra_config_json = dumps(
                updated.extra_config or {}, ensure_ascii=False
            )
            row.adapter_kind = updated.adapter_kind
            row.capability_metadata_json = dumps(
                updated.capability_metadata or {}, ensure_ascii=False
            )
            row.default_options_json = dumps(
                updated.default_options or {}, ensure_ascii=False
            )
            row.capability_provenance_json = dumps(
                updated.capability_provenance or {}, ensure_ascii=False
            )
            row.updated_at = _epoch_ms()
            await session.commit()
        return updated

    async def delete_source(
        self,
        *,
        source_id: str,
    ) -> bool:
        async with get_session() as session:
            result = await session.execute(
                delete(AISource).where(AISource.source_id == source_id)
            )
            await session.commit()
        return rowcount(result) > 0

    async def build_delete_dependency_report(
        self,
        *,
        source_id: str,
    ) -> AISourceDeleteDependencyReport | None:
        from apeiria.ai.model.catalog.registry import (
            SOURCE_MODEL_CAPABILITY_REGISTRY,
        )

        source = await self.get_source(source_id=source_id)
        if source is None:
            return None
        entry = SOURCE_MODEL_CAPABILITY_REGISTRY[source.capability_type]
        models = await entry.list_models(source_id)
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
        return None

    @staticmethod
    def _orm_to_definition(row: AISource) -> AISourceDefinition:
        custom_headers = safe_json_loads(row.custom_headers_json, default={})
        extra_config = safe_json_loads(row.extra_config_json, default={})
        capability_metadata = safe_json_loads(row.capability_metadata_json, default={})
        default_options = safe_json_loads(row.default_options_json, default={})
        capability_provenance = safe_json_loads(
            row.capability_provenance_json, default={}
        )
        client_type = cast("AISourceClientType", str(row.client_type))
        raw_adapter_kind = row.adapter_kind
        adapter_kind = cast(
            "AIModelAdapterKind",
            (
                raw_adapter_kind.strip()
                if isinstance(raw_adapter_kind, str) and raw_adapter_kind.strip()
                else resolve_adapter_kind_for_client_type(client_type)
            ),
        )
        return AISourceDefinition(
            source_id=str(row.source_id),
            name=str(row.name),
            capability_type=cast("AISourceCapabilityType", str(row.capability_type)),
            client_type=client_type,
            preset_type=cast("AISourcePresetType", str(row.preset_type)),
            api_base=str(row.api_base) if row.api_base is not None else None,
            enabled=bool(row.enabled),
            timeout_seconds=row.timeout_seconds,
            custom_headers=(custom_headers if isinstance(custom_headers, dict) else {}),
            extra_config=extra_config if isinstance(extra_config, dict) else {},
            adapter_kind=adapter_kind,
            capability_metadata=(
                capability_metadata if isinstance(capability_metadata, dict) else {}
            ),
            default_options=(
                default_options if isinstance(default_options, dict) else {}
            ),
            capability_provenance=(
                capability_provenance if isinstance(capability_provenance, dict) else {}
            ),
        )


def _extract_inline_api_key(source: AISourceDefinition) -> str | None:
    extra_config = source.extra_config or {}
    raw_api_keys = extra_config.get("api_keys")
    if not isinstance(raw_api_keys, list):
        return None
    for value in raw_api_keys:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None

"""Source registry CRUD service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from json import dumps
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from apeiria.ai.model.sources.models import (
    SOURCE_PRESETS,
    AISourceCapabilityType,
    AISourceClientType,
    AISourceDefinition,
    AISourcePresetDefinition,
    AISourcePresetType,
    resolve_adapter_kind_for_client_type,
)
from apeiria.db.runtime import database_runtime
from apeiria.utils.json_utils import safe_json_loads

if TYPE_CHECKING:
    from apeiria.ai.model.runtime.capabilities import AIModelAdapterKind

_ADAPTER_KIND_COLUMN_INDEX = 10
_CAPABILITY_METADATA_COLUMN_INDEX = 11
_DEFAULT_OPTIONS_COLUMN_INDEX = 12
_CAPABILITY_PROVENANCE_COLUMN_INDEX = 13


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
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT
                    source_id,
                    name,
                    capability_type,
                    client_type,
                    preset_type,
                    api_base,
                    enabled,
                    timeout_seconds,
                    custom_headers_json,
                    extra_config_json,
                    adapter_kind,
                    capability_metadata_json,
                    default_options_json,
                    capability_provenance_json
                FROM ai_source
                ORDER BY name ASC, source_id ASC
                """
            ).fetchall()
        return [self._row_to_definition(row) for row in rows]

    async def get_source(
        self,
        *,
        source_id: str,
    ) -> AISourceDefinition | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                """
                SELECT
                    source_id,
                    name,
                    capability_type,
                    client_type,
                    preset_type,
                    api_base,
                    enabled,
                    timeout_seconds,
                    custom_headers_json,
                    extra_config_json,
                    adapter_kind,
                    capability_metadata_json,
                    default_options_json,
                    capability_provenance_json
                FROM ai_source
                WHERE source_id = ?
                """,
                (source_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_definition(row)

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
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                INSERT INTO ai_source (
                    source_id,
                    name,
                    capability_type,
                    client_type,
                    preset_type,
                    api_base,
                    enabled,
                    timeout_seconds,
                    custom_headers_json,
                    extra_config_json,
                    adapter_kind,
                    capability_metadata_json,
                    default_options_json,
                    capability_provenance_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source.source_id,
                    source.name,
                    source.capability_type,
                    source.client_type,
                    source.preset_type,
                    source.api_base,
                    1 if source.enabled else 0,
                    source.timeout_seconds,
                    dumps(source.custom_headers or {}, ensure_ascii=False),
                    dumps(source.extra_config or {}, ensure_ascii=False),
                    source.adapter_kind,
                    dumps(source.capability_metadata or {}, ensure_ascii=False),
                    dumps(source.default_options or {}, ensure_ascii=False),
                    dumps(source.capability_provenance or {}, ensure_ascii=False),
                    _utcnow_text(),
                ),
            )
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
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE ai_source
                SET
                    name = ?,
                    capability_type = ?,
                    client_type = ?,
                    preset_type = ?,
                    api_base = ?,
                    enabled = ?,
                    timeout_seconds = ?,
                    custom_headers_json = ?,
                    extra_config_json = ?,
                    adapter_kind = ?,
                    capability_metadata_json = ?,
                    default_options_json = ?,
                    capability_provenance_json = ?,
                    updated_at = ?
                WHERE source_id = ?
                """,
                (
                    updated.name,
                    updated.capability_type,
                    updated.client_type,
                    updated.preset_type,
                    updated.api_base,
                    1 if updated.enabled else 0,
                    updated.timeout_seconds,
                    dumps(updated.custom_headers or {}, ensure_ascii=False),
                    dumps(updated.extra_config or {}, ensure_ascii=False),
                    updated.adapter_kind,
                    dumps(updated.capability_metadata or {}, ensure_ascii=False),
                    dumps(updated.default_options or {}, ensure_ascii=False),
                    dumps(updated.capability_provenance or {}, ensure_ascii=False),
                    _utcnow_text(),
                    source_id,
                ),
            )
        return updated

    async def delete_source(
        self,
        *,
        source_id: str,
    ) -> bool:
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                "DELETE FROM ai_source WHERE source_id = ?",
                (source_id,),
            )
        return cursor.rowcount > 0

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
    def _row_to_definition(row: tuple[object, ...]) -> AISourceDefinition:
        custom_headers = safe_json_loads(
            str(row[8]) if row[8] is not None else None,
            default={},
        )
        extra_config = safe_json_loads(
            str(row[9]) if row[9] is not None else None,
            default={},
        )
        capability_metadata = safe_json_loads(
            (
                str(row[_CAPABILITY_METADATA_COLUMN_INDEX])
                if len(row) > _CAPABILITY_METADATA_COLUMN_INDEX
                and row[_CAPABILITY_METADATA_COLUMN_INDEX] is not None
                else None
            ),
            default={},
        )
        default_options = safe_json_loads(
            (
                str(row[_DEFAULT_OPTIONS_COLUMN_INDEX])
                if len(row) > _DEFAULT_OPTIONS_COLUMN_INDEX
                and row[_DEFAULT_OPTIONS_COLUMN_INDEX] is not None
                else None
            ),
            default={},
        )
        capability_provenance = safe_json_loads(
            (
                str(row[_CAPABILITY_PROVENANCE_COLUMN_INDEX])
                if len(row) > _CAPABILITY_PROVENANCE_COLUMN_INDEX
                and row[_CAPABILITY_PROVENANCE_COLUMN_INDEX] is not None
                else None
            ),
            default={},
        )
        client_type = cast("AISourceClientType", str(row[3]))
        raw_adapter_kind = (
            row[_ADAPTER_KIND_COLUMN_INDEX]
            if len(row) > _ADAPTER_KIND_COLUMN_INDEX
            else None
        )
        adapter_kind = cast(
            "AIModelAdapterKind",
            (
                raw_adapter_kind.strip()
                if isinstance(raw_adapter_kind, str) and raw_adapter_kind.strip()
                else resolve_adapter_kind_for_client_type(client_type)
            ),
        )
        return AISourceDefinition(
            source_id=str(row[0]),
            name=str(row[1]),
            capability_type=cast("AISourceCapabilityType", str(row[2])),
            client_type=client_type,
            preset_type=cast("AISourcePresetType", str(row[4])),
            api_base=str(row[5]) if row[5] is not None else None,
            enabled=bool(row[6]),
            timeout_seconds=_coerce_optional_int(row[7]),
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


def _utcnow_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        return int(value.strip())
    return None

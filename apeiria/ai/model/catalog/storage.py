"""SQLAlchemy async storage helpers for admin-managed source models."""

from __future__ import annotations

from dataclasses import dataclass
from json import dumps
from typing import TYPE_CHECKING, TypeAlias

from sqlalchemy import delete, select, update

from apeiria.db.base import _epoch_ms
from apeiria.db.engine import get_session, rowcount
from apeiria.db.models.ai_source import (
    AIChatModel,
    AIEmbeddingModel,
    AIRerankModel,
    AISTTModel,
    AITTSModel,
)
from apeiria.utils.json_utils import safe_json_loads

if TYPE_CHECKING:
    from apeiria.db.base import Base

SourceModelClass: TypeAlias = (
    type[AIChatModel]
    | type[AIEmbeddingModel]
    | type[AISTTModel]
    | type[AITTSModel]
    | type[AIRerankModel]
)

_ALLOWED_MODEL_CLASSES: set[type] = {
    AIChatModel,
    AIEmbeddingModel,
    AISTTModel,
    AITTSModel,
    AIRerankModel,
}


class UnsupportedSourceModelTableError(ValueError):
    """Raised when source model storage is asked to use an unknown model class."""

    def __init__(self, model_cls: type) -> None:
        super().__init__(f"unsupported source model class: {model_cls}")


@dataclass(frozen=True)
class SourceModelRecord:
    """One persisted source model record."""

    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    enabled: bool
    is_default: bool
    extra_params: dict[str, object]
    capability_metadata: dict[str, object]
    default_options: dict[str, object]
    capability_provenance: dict[str, object]


async def get_source_model(
    model_cls: SourceModelClass,
    *,
    model_id: str,
) -> SourceModelRecord | None:
    _validate_model_cls(model_cls)
    async with get_session() as session:
        row = await session.get(model_cls, model_id)
    return _orm_to_record(row)


async def list_source_models(
    model_cls: SourceModelClass,
    *,
    source_id: str,
) -> list[SourceModelRecord]:
    _validate_model_cls(model_cls)
    async with get_session() as session:
        result = await session.execute(
            select(model_cls)
            .where(model_cls.source_id == source_id)
            .order_by(
                model_cls.is_default.desc(),
                model_cls.display_name.asc(),
                model_cls.model_id.asc(),
            )
        )
        rows = result.scalars().all()
    return [r for row in rows if (r := _orm_to_record(row)) is not None]


async def list_all_source_models(
    model_cls: SourceModelClass,
) -> list[SourceModelRecord]:
    _validate_model_cls(model_cls)
    async with get_session() as session:
        result = await session.execute(
            select(model_cls).order_by(
                model_cls.source_id.asc(),
                model_cls.is_default.desc(),
                model_cls.display_name.asc(),
                model_cls.model_id.asc(),
            )
        )
        rows = result.scalars().all()
    return [r for row in rows if (r := _orm_to_record(row)) is not None]


async def create_source_model(  # noqa: PLR0913
    model_cls: SourceModelClass,
    *,
    model_id: str,
    source_id: str,
    model_identifier: str,
    display_name: str,
    enabled: bool,
    is_default: bool,
    extra_params: dict[str, object] | None,
    capability_metadata: dict[str, object] | None = None,
    default_options: dict[str, object] | None = None,
    capability_provenance: dict[str, object] | None = None,
) -> SourceModelRecord:
    _validate_model_cls(model_cls)
    now = _epoch_ms()
    async with get_session() as session:
        if is_default:
            await _clear_default_source_model(session, model_cls, source_id=source_id)
        instance = model_cls(
            model_id=model_id,
            source_id=source_id,
            model_identifier=model_identifier,
            display_name=display_name,
            enabled=1 if enabled else 0,
            is_default=1 if is_default else 0,
            extra_params_json=dumps(extra_params or {}, ensure_ascii=False),
            capability_metadata_json=dumps(
                capability_metadata or {}, ensure_ascii=False
            ),
            default_options_json=dumps(default_options or {}, ensure_ascii=False),
            capability_provenance_json=dumps(
                capability_provenance or {}, ensure_ascii=False
            ),
            updated_at=now,
        )
        session.add(instance)
        await session.commit()
    return SourceModelRecord(
        model_id=model_id,
        source_id=source_id,
        model_identifier=model_identifier,
        display_name=display_name,
        enabled=enabled,
        is_default=is_default,
        extra_params=extra_params or {},
        capability_metadata=capability_metadata or {},
        default_options=default_options or {},
        capability_provenance=capability_provenance or {},
    )


async def update_source_model(  # noqa: PLR0913
    model_cls: SourceModelClass,
    *,
    model_id: str,
    source_id: str,
    model_identifier: str,
    display_name: str,
    enabled: bool,
    is_default: bool,
    extra_params: dict[str, object] | None,
    capability_metadata: dict[str, object] | None = None,
    default_options: dict[str, object] | None = None,
    capability_provenance: dict[str, object] | None = None,
) -> SourceModelRecord | None:
    _validate_model_cls(model_cls)
    async with get_session() as session:
        existing = await session.get(model_cls, model_id)
        if existing is None:
            return None
        if is_default:
            await _clear_default_source_model(session, model_cls, source_id=source_id)
        existing.source_id = source_id
        existing.model_identifier = model_identifier
        existing.display_name = display_name
        existing.enabled = 1 if enabled else 0
        existing.is_default = 1 if is_default else 0
        existing.extra_params_json = dumps(extra_params or {}, ensure_ascii=False)
        existing.capability_metadata_json = dumps(
            capability_metadata or {}, ensure_ascii=False
        )
        existing.default_options_json = dumps(default_options or {}, ensure_ascii=False)
        existing.capability_provenance_json = dumps(
            capability_provenance or {}, ensure_ascii=False
        )
        existing.updated_at = _epoch_ms()
        await session.commit()
    return SourceModelRecord(
        model_id=model_id,
        source_id=source_id,
        model_identifier=model_identifier,
        display_name=display_name,
        enabled=enabled,
        is_default=is_default,
        extra_params=extra_params or {},
        capability_metadata=capability_metadata or {},
        default_options=default_options or {},
        capability_provenance=capability_provenance or {},
    )


async def delete_source_model(
    model_cls: SourceModelClass,
    *,
    model_id: str,
) -> bool:
    _validate_model_cls(model_cls)
    async with get_session() as session:
        result = await session.execute(
            delete(model_cls).where(model_cls.model_id == model_id)
        )
        await session.commit()
    return rowcount(result) > 0


async def clear_default_source_model(
    model_cls: SourceModelClass,
    *,
    source_id: str,
) -> None:
    _validate_model_cls(model_cls)
    async with get_session() as session:
        await _clear_default_source_model(session, model_cls, source_id=source_id)
        await session.commit()


def _orm_to_record(row: "Base | None") -> SourceModelRecord | None:
    if row is None:
        return None
    extra_params = safe_json_loads(row.extra_params_json, default={})
    capability_metadata = safe_json_loads(row.capability_metadata_json, default={})
    default_options = safe_json_loads(row.default_options_json, default={})
    capability_provenance = safe_json_loads(row.capability_provenance_json, default={})
    return SourceModelRecord(
        model_id=str(row.model_id),
        source_id=str(row.source_id),
        model_identifier=str(row.model_identifier),
        display_name=str(row.display_name),
        enabled=bool(row.enabled),
        is_default=bool(row.is_default),
        extra_params=extra_params if isinstance(extra_params, dict) else {},
        capability_metadata=(
            capability_metadata if isinstance(capability_metadata, dict) else {}
        ),
        default_options=default_options if isinstance(default_options, dict) else {},
        capability_provenance=(
            capability_provenance if isinstance(capability_provenance, dict) else {}
        ),
    )


async def _clear_default_source_model(
    session: object,
    model_cls: SourceModelClass,
    *,
    source_id: str,
) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession

    assert isinstance(session, AsyncSession)
    await session.execute(
        update(model_cls)
        .where(model_cls.source_id == source_id)
        .values(is_default=0, updated_at=_epoch_ms())
    )


def _validate_model_cls(model_cls: type) -> None:
    if model_cls not in _ALLOWED_MODEL_CLASSES:
        raise UnsupportedSourceModelTableError(model_cls)

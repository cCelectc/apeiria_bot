"""Speech-to-text model CRUD service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import select

from apeiria.ai.model.source_models import AISpeechToTextModelDefinition
from apeiria.db.models import AISTTModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AISTTModelCreateInput:
    """Create or update payload for one STT model."""

    source_id: str
    model_identifier: str
    display_name: str
    enabled: bool = True
    is_default: bool = False
    extra_params: dict[str, Any] | None = None


class AISTTModelService:
    """Speech-to-text model CRUD service."""

    async def get_model(
        self,
        session: "AsyncSession",
        *,
        model_id: str,
    ) -> AISpeechToTextModelDefinition | None:
        result = await session.execute(
            select(AISTTModel).where(AISTTModel.model_id == model_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return AISpeechToTextModelDefinition(
            model_id=row.model_id,
            source_id=row.source_id,
            model_identifier=row.model_identifier,
            display_name=row.display_name,
            enabled=row.enabled,
            is_default=row.is_default,
            extra_params=row.extra_params_json or {},
        )

    async def list_models(
        self,
        session: "AsyncSession",
        *,
        source_id: str,
    ) -> list[AISpeechToTextModelDefinition]:
        result = await session.execute(
            select(AISTTModel)
            .where(AISTTModel.source_id == source_id)
            .order_by(
                AISTTModel.is_default.desc(),
                AISTTModel.display_name.asc(),
                AISTTModel.id.asc(),
            )
        )
        return [
            AISpeechToTextModelDefinition(
                model_id=row.model_id,
                source_id=row.source_id,
                model_identifier=row.model_identifier,
                display_name=row.display_name,
                enabled=row.enabled,
                is_default=row.is_default,
                extra_params=row.extra_params_json or {},
            )
            for row in result.scalars().all()
        ]

    async def create_model(
        self,
        session: "AsyncSession",
        create_input: AISTTModelCreateInput,
    ) -> AISTTModel:
        if create_input.is_default:
            await self._clear_default(session, source_id=create_input.source_id)
        row = AISTTModel(
            model_id=f"stt_model_{uuid4().hex}",
            source_id=create_input.source_id,
            model_identifier=create_input.model_identifier,
            display_name=create_input.display_name,
            enabled=create_input.enabled,
            is_default=create_input.is_default,
            extra_params_json=create_input.extra_params or {},
        )
        session.add(row)
        await session.flush()
        return row

    async def update_model(
        self,
        session: "AsyncSession",
        *,
        model_id: str,
        create_input: AISTTModelCreateInput,
    ) -> AISTTModel | None:
        result = await session.execute(
            select(AISTTModel).where(AISTTModel.model_id == model_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if create_input.is_default:
            await self._clear_default(session, source_id=create_input.source_id)
        row.source_id = create_input.source_id
        row.model_identifier = create_input.model_identifier
        row.display_name = create_input.display_name
        row.enabled = create_input.enabled
        row.is_default = create_input.is_default
        row.extra_params_json = create_input.extra_params or {}
        await session.flush()
        return row

    async def delete_model(
        self,
        session: "AsyncSession",
        *,
        model_id: str,
    ) -> bool:
        result = await session.execute(
            select(AISTTModel).where(AISTTModel.model_id == model_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await session.delete(row)
        await session.flush()
        return True

    async def _clear_default(
        self,
        session: "AsyncSession",
        *,
        source_id: str,
    ) -> None:
        result = await session.execute(
            select(AISTTModel).where(AISTTModel.source_id == source_id)
        )
        for row in result.scalars().all():
            row.is_default = False
        await session.flush()


ai_stt_model_service = AISTTModelService()

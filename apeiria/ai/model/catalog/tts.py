"""Text-to-speech model CRUD service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from apeiria.ai.model.catalog.models import AITextToSpeechModelDefinition
from apeiria.ai.model.catalog.storage import (
    create_source_model,
    delete_source_model,
    get_source_model,
    list_source_models,
    update_source_model,
)
from apeiria.db.models.ai_source import AITTSModel


@dataclass(frozen=True)
class AITTSModelCreateInput:
    """Create or update payload for one TTS model."""

    source_id: str
    model_identifier: str
    display_name: str
    enabled: bool = True
    is_default: bool = False
    extra_params: dict[str, Any] | None = None
    capability_metadata: dict[str, Any] | None = None
    default_options: dict[str, Any] | None = None
    capability_provenance: dict[str, Any] | None = None


class AITTSModelService:
    """Text-to-speech model CRUD service."""

    async def get_model(
        self,
        *,
        model_id: str,
    ) -> AITextToSpeechModelDefinition | None:
        record = await get_source_model(AITTSModel, model_id=model_id)
        return (
            None if record is None else AITextToSpeechModelDefinition(**record.__dict__)
        )

    async def list_models(
        self,
        *,
        source_id: str,
    ) -> list[AITextToSpeechModelDefinition]:
        return [
            AITextToSpeechModelDefinition(**row.__dict__)
            for row in await list_source_models(AITTSModel, source_id=source_id)
        ]

    async def create_model(
        self,
        create_input: AITTSModelCreateInput,
    ) -> AITextToSpeechModelDefinition:
        record = await create_source_model(
            AITTSModel,
            model_id=f"tts_model_{uuid4().hex}",
            source_id=create_input.source_id,
            model_identifier=create_input.model_identifier,
            display_name=create_input.display_name,
            enabled=create_input.enabled,
            is_default=create_input.is_default,
            extra_params=create_input.extra_params,
            capability_metadata=create_input.capability_metadata,
            default_options=create_input.default_options,
            capability_provenance=create_input.capability_provenance,
        )
        return AITextToSpeechModelDefinition(**record.__dict__)

    async def update_model(
        self,
        *,
        model_id: str,
        create_input: AITTSModelCreateInput,
    ) -> AITextToSpeechModelDefinition | None:
        record = await update_source_model(
            AITTSModel,
            model_id=model_id,
            source_id=create_input.source_id,
            model_identifier=create_input.model_identifier,
            display_name=create_input.display_name,
            enabled=create_input.enabled,
            is_default=create_input.is_default,
            extra_params=create_input.extra_params,
            capability_metadata=create_input.capability_metadata,
            default_options=create_input.default_options,
            capability_provenance=create_input.capability_provenance,
        )
        return (
            None if record is None else AITextToSpeechModelDefinition(**record.__dict__)
        )

    async def delete_model(
        self,
        *,
        model_id: str,
    ) -> bool:
        return await delete_source_model(AITTSModel, model_id=model_id)

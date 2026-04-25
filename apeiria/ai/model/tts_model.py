"""Text-to-speech model CRUD service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from apeiria.ai.model.source_model_storage import (
    create_source_model,
    delete_source_model,
    get_source_model,
    list_source_models,
    update_source_model,
)
from apeiria.ai.model.source_models import AITextToSpeechModelDefinition

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AITTSModelCreateInput:
    """Create or update payload for one TTS model."""

    source_id: str
    model_identifier: str
    display_name: str
    enabled: bool = True
    is_default: bool = False
    extra_params: dict[str, Any] | None = None


class AITTSModelService:
    """Text-to-speech model CRUD service."""

    async def get_model(
        self,
        session: "AsyncSession | None",
        *,
        model_id: str,
    ) -> AITextToSpeechModelDefinition | None:
        del session
        record = get_source_model("ai_tts_model", model_id=model_id)
        return (
            None
            if record is None
            else AITextToSpeechModelDefinition(**record.__dict__)
        )

    async def list_models(
        self,
        session: "AsyncSession | None",
        *,
        source_id: str,
    ) -> list[AITextToSpeechModelDefinition]:
        del session
        return [
            AITextToSpeechModelDefinition(**row.__dict__)
            for row in list_source_models("ai_tts_model", source_id=source_id)
        ]

    async def create_model(
        self,
        session: "AsyncSession | None",
        create_input: AITTSModelCreateInput,
    ) -> AITextToSpeechModelDefinition:
        del session
        return AITextToSpeechModelDefinition(
            **create_source_model(
                "ai_tts_model",
                model_id=f"tts_model_{uuid4().hex}",
                source_id=create_input.source_id,
                model_identifier=create_input.model_identifier,
                display_name=create_input.display_name,
                enabled=create_input.enabled,
                is_default=create_input.is_default,
                extra_params=create_input.extra_params,
            ).__dict__
        )

    async def update_model(
        self,
        session: "AsyncSession | None",
        *,
        model_id: str,
        create_input: AITTSModelCreateInput,
    ) -> AITextToSpeechModelDefinition | None:
        del session
        record = update_source_model(
            "ai_tts_model",
            model_id=model_id,
            source_id=create_input.source_id,
            model_identifier=create_input.model_identifier,
            display_name=create_input.display_name,
            enabled=create_input.enabled,
            is_default=create_input.is_default,
            extra_params=create_input.extra_params,
        )
        return (
            None
            if record is None
            else AITextToSpeechModelDefinition(**record.__dict__)
        )

    async def delete_model(
        self,
        session: "AsyncSession | None",
        *,
        model_id: str,
    ) -> bool:
        del session
        return delete_source_model("ai_tts_model", model_id=model_id)


ai_tts_model_service = AITTSModelService()

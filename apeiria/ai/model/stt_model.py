"""Speech-to-text model CRUD service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from apeiria.ai.model.source_model_storage import (
    create_source_model,
    delete_source_model,
    get_source_model,
    list_source_models,
    update_source_model,
)
from apeiria.ai.model.source_models import AISpeechToTextModelDefinition


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
        *,
        model_id: str,
    ) -> AISpeechToTextModelDefinition | None:
        record = get_source_model("ai_stt_model", model_id=model_id)
        return (
            None if record is None else AISpeechToTextModelDefinition(**record.__dict__)
        )

    async def list_models(
        self,
        *,
        source_id: str,
    ) -> list[AISpeechToTextModelDefinition]:
        return [
            AISpeechToTextModelDefinition(**row.__dict__)
            for row in list_source_models("ai_stt_model", source_id=source_id)
        ]

    async def create_model(
        self,
        create_input: AISTTModelCreateInput,
    ) -> AISpeechToTextModelDefinition:
        return AISpeechToTextModelDefinition(
            **create_source_model(
                "ai_stt_model",
                model_id=f"stt_model_{uuid4().hex}",
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
        *,
        model_id: str,
        create_input: AISTTModelCreateInput,
    ) -> AISpeechToTextModelDefinition | None:
        record = update_source_model(
            "ai_stt_model",
            model_id=model_id,
            source_id=create_input.source_id,
            model_identifier=create_input.model_identifier,
            display_name=create_input.display_name,
            enabled=create_input.enabled,
            is_default=create_input.is_default,
            extra_params=create_input.extra_params,
        )
        return (
            None if record is None else AISpeechToTextModelDefinition(**record.__dict__)
        )

    async def delete_model(
        self,
        *,
        model_id: str,
    ) -> bool:
        return delete_source_model("ai_stt_model", model_id=model_id)


ai_stt_model_service = AISTTModelService()

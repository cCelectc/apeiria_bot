"""Chat model CRUD service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from apeiria.ai.model.chat_models import AIChatModelDefinition
from apeiria.ai.model.source_model_storage import (
    create_source_model,
    delete_source_model,
    get_source_model,
    list_all_source_models,
    list_source_models,
    update_source_model,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AIChatModelCreateInput:
    """Create or update payload for one chat model."""

    source_id: str
    model_identifier: str
    display_name: str
    enabled: bool = True
    is_default: bool = False
    extra_params: dict[str, Any] | None = None


class AIChatModelService:
    """Chat model CRUD service."""

    async def get_model(
        self,
        session: "AsyncSession | None",
        *,
        model_id: str,
    ) -> AIChatModelDefinition | None:
        del session
        record = get_source_model("ai_chat_model", model_id=model_id)
        return (
            None
            if record is None
            else AIChatModelDefinition(
                model_id=record.model_id,
                source_id=record.source_id,
                model_identifier=record.model_identifier,
                display_name=record.display_name,
                enabled=record.enabled,
                is_default=record.is_default,
                extra_params=record.extra_params,
            )
        )

    async def list_all_models(
        self,
        session: "AsyncSession | None",
    ) -> list[AIChatModelDefinition]:
        del session
        return [
            AIChatModelDefinition(
                model_id=row.model_id,
                source_id=row.source_id,
                model_identifier=row.model_identifier,
                display_name=row.display_name,
                enabled=row.enabled,
                is_default=row.is_default,
                extra_params=row.extra_params,
            )
            for row in list_all_source_models("ai_chat_model")
        ]

    async def list_models(
        self,
        session: "AsyncSession | None",
        *,
        source_id: str,
    ) -> list[AIChatModelDefinition]:
        del session
        return [
            AIChatModelDefinition(
                model_id=row.model_id,
                source_id=row.source_id,
                model_identifier=row.model_identifier,
                display_name=row.display_name,
                enabled=row.enabled,
                is_default=row.is_default,
                extra_params=row.extra_params,
            )
            for row in list_source_models("ai_chat_model", source_id=source_id)
        ]

    async def create_model(
        self,
        session: "AsyncSession | None",
        create_input: AIChatModelCreateInput,
    ) -> AIChatModelDefinition:
        del session
        return AIChatModelDefinition(
            **create_source_model(
                "ai_chat_model",
                model_id=f"model_{uuid4().hex}",
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
        create_input: AIChatModelCreateInput,
    ) -> AIChatModelDefinition | None:
        del session
        record = update_source_model(
            "ai_chat_model",
            model_id=model_id,
            source_id=create_input.source_id,
            model_identifier=create_input.model_identifier,
            display_name=create_input.display_name,
            enabled=create_input.enabled,
            is_default=create_input.is_default,
            extra_params=create_input.extra_params,
        )
        return None if record is None else AIChatModelDefinition(**record.__dict__)

    async def delete_model(
        self,
        session: "AsyncSession | None",
        *,
        model_id: str,
    ) -> bool:
        del session
        return delete_source_model("ai_chat_model", model_id=model_id)


ai_chat_model_service = AIChatModelService()

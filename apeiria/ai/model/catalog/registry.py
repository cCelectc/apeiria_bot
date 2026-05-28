"""Capability-oriented model service registry."""
# ruff: noqa: PLR0913, FBT001, C901

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.ai.model.catalog.chat import (
    AIChatModelCreateInput,
    AIChatModelService,
)
from apeiria.ai.model.catalog.embedding import (
    AIEmbeddingModelCreateInput,
    AIEmbeddingModelService,
)
from apeiria.ai.model.catalog.models import AISourceModelDefinition
from apeiria.ai.model.catalog.rerank import (
    AIRerankModelCreateInput,
    AIRerankModelService,
)
from apeiria.ai.model.catalog.stt import (
    AISTTModelCreateInput,
    AISTTModelService,
)
from apeiria.ai.model.catalog.tts import (
    AITTSModelCreateInput,
    AITTSModelService,
)

if TYPE_CHECKING:
    from apeiria.ai.model.sources.models import AISourceCapabilityType


ModelListFn = Callable[[str], Awaitable[list[AISourceModelDefinition]]]
ModelGetFn = Callable[[str], Awaitable[AISourceModelDefinition | None]]
ModelCreateFn = Callable[
    [
        str,
        str,
        str,
        bool,
        bool,
        dict[str, object],
        dict[str, object] | None,
        dict[str, object] | None,
        dict[str, object] | None,
    ],
    Awaitable[AISourceModelDefinition],
]
ModelUpdateFn = Callable[
    [
        str,
        str,
        str,
        str,
        bool,
        bool,
        dict[str, object],
        dict[str, object] | None,
        dict[str, object] | None,
        dict[str, object] | None,
    ],
    Awaitable[AISourceModelDefinition | None],
]
ModelDeleteFn = Callable[[str], Awaitable[bool]]


@dataclass(frozen=True)
class AICapabilityModelRegistryEntry:
    """One capability-specific source model manager entry."""

    capability_type: "AISourceCapabilityType"
    get_model: ModelGetFn
    list_models: ModelListFn
    create_model: ModelCreateFn
    update_model: ModelUpdateFn
    delete_model: ModelDeleteFn


def build_source_model_capability_registry(
    *,
    chat_model_service: AIChatModelService | None = None,
    embedding_model_service: AIEmbeddingModelService | None = None,
    rerank_model_service: AIRerankModelService | None = None,
    stt_model_service: AISTTModelService | None = None,
    tts_model_service: AITTSModelService | None = None,
) -> dict["AISourceCapabilityType", AICapabilityModelRegistryEntry]:
    chat_service = chat_model_service or AIChatModelService()
    embedding_service = embedding_model_service or AIEmbeddingModelService()
    rerank_service = rerank_model_service or AIRerankModelService()
    stt_service = stt_model_service or AISTTModelService()
    tts_service = tts_model_service or AITTSModelService()

    async def get_chat_model(model_id: str) -> AISourceModelDefinition | None:
        return await chat_service.get_model(model_id=model_id)

    async def list_chat_models(source_id: str) -> list[AISourceModelDefinition]:
        return list(await chat_service.list_models(source_id=source_id))

    async def create_chat_model(
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        capability_metadata: dict[str, object] | None,
        default_options: dict[str, object] | None,
        capability_provenance: dict[str, object] | None,
    ) -> AISourceModelDefinition:
        return await chat_service.create_model(
            AIChatModelCreateInput(
                source_id=source_id,
                model_identifier=model_identifier,
                display_name=display_name,
                enabled=enabled,
                is_default=is_default,
                extra_params=extra_params,
                capability_metadata=capability_metadata,
                default_options=default_options,
                capability_provenance=capability_provenance,
            ),
        )

    async def update_chat_model(
        model_id: str,
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        capability_metadata: dict[str, object] | None,
        default_options: dict[str, object] | None,
        capability_provenance: dict[str, object] | None,
    ) -> AISourceModelDefinition | None:
        return await chat_service.update_model(
            model_id=model_id,
            create_input=AIChatModelCreateInput(
                source_id=source_id,
                model_identifier=model_identifier,
                display_name=display_name,
                enabled=enabled,
                is_default=is_default,
                extra_params=extra_params,
                capability_metadata=capability_metadata,
                default_options=default_options,
                capability_provenance=capability_provenance,
            ),
        )

    async def delete_chat_model(model_id: str) -> bool:
        return await chat_service.delete_model(model_id=model_id)

    async def get_embedding_model(model_id: str) -> AISourceModelDefinition | None:
        return await embedding_service.get_model(model_id=model_id)

    async def list_embedding_models(source_id: str) -> list[AISourceModelDefinition]:
        return list(await embedding_service.list_models(source_id=source_id))

    async def create_embedding_model(
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        capability_metadata: dict[str, object] | None,
        default_options: dict[str, object] | None,
        capability_provenance: dict[str, object] | None,
    ) -> AISourceModelDefinition:
        return await embedding_service.create_model(
            AIEmbeddingModelCreateInput(
                source_id=source_id,
                model_identifier=model_identifier,
                display_name=display_name,
                enabled=enabled,
                is_default=is_default,
                extra_params=extra_params,
                capability_metadata=capability_metadata,
                default_options=default_options,
                capability_provenance=capability_provenance,
            ),
        )

    async def update_embedding_model(
        model_id: str,
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        capability_metadata: dict[str, object] | None,
        default_options: dict[str, object] | None,
        capability_provenance: dict[str, object] | None,
    ) -> AISourceModelDefinition | None:
        return await embedding_service.update_model(
            model_id=model_id,
            create_input=AIEmbeddingModelCreateInput(
                source_id=source_id,
                model_identifier=model_identifier,
                display_name=display_name,
                enabled=enabled,
                is_default=is_default,
                extra_params=extra_params,
                capability_metadata=capability_metadata,
                default_options=default_options,
                capability_provenance=capability_provenance,
            ),
        )

    async def delete_embedding_model(model_id: str) -> bool:
        return await embedding_service.delete_model(model_id=model_id)

    async def get_stt_model(model_id: str) -> AISourceModelDefinition | None:
        return await stt_service.get_model(model_id=model_id)

    async def list_stt_models(source_id: str) -> list[AISourceModelDefinition]:
        return list(await stt_service.list_models(source_id=source_id))

    async def create_stt_model(
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        capability_metadata: dict[str, object] | None,
        default_options: dict[str, object] | None,
        capability_provenance: dict[str, object] | None,
    ) -> AISourceModelDefinition:
        return await stt_service.create_model(
            AISTTModelCreateInput(
                source_id=source_id,
                model_identifier=model_identifier,
                display_name=display_name,
                enabled=enabled,
                is_default=is_default,
                extra_params=extra_params,
                capability_metadata=capability_metadata,
                default_options=default_options,
                capability_provenance=capability_provenance,
            ),
        )

    async def update_stt_model(
        model_id: str,
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        capability_metadata: dict[str, object] | None,
        default_options: dict[str, object] | None,
        capability_provenance: dict[str, object] | None,
    ) -> AISourceModelDefinition | None:
        return await stt_service.update_model(
            model_id=model_id,
            create_input=AISTTModelCreateInput(
                source_id=source_id,
                model_identifier=model_identifier,
                display_name=display_name,
                enabled=enabled,
                is_default=is_default,
                extra_params=extra_params,
                capability_metadata=capability_metadata,
                default_options=default_options,
                capability_provenance=capability_provenance,
            ),
        )

    async def delete_stt_model(model_id: str) -> bool:
        return await stt_service.delete_model(model_id=model_id)

    async def get_tts_model(model_id: str) -> AISourceModelDefinition | None:
        return await tts_service.get_model(model_id=model_id)

    async def list_tts_models(source_id: str) -> list[AISourceModelDefinition]:
        return list(await tts_service.list_models(source_id=source_id))

    async def create_tts_model(
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        capability_metadata: dict[str, object] | None,
        default_options: dict[str, object] | None,
        capability_provenance: dict[str, object] | None,
    ) -> AISourceModelDefinition:
        return await tts_service.create_model(
            AITTSModelCreateInput(
                source_id=source_id,
                model_identifier=model_identifier,
                display_name=display_name,
                enabled=enabled,
                is_default=is_default,
                extra_params=extra_params,
                capability_metadata=capability_metadata,
                default_options=default_options,
                capability_provenance=capability_provenance,
            ),
        )

    async def update_tts_model(
        model_id: str,
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        capability_metadata: dict[str, object] | None,
        default_options: dict[str, object] | None,
        capability_provenance: dict[str, object] | None,
    ) -> AISourceModelDefinition | None:
        return await tts_service.update_model(
            model_id=model_id,
            create_input=AITTSModelCreateInput(
                source_id=source_id,
                model_identifier=model_identifier,
                display_name=display_name,
                enabled=enabled,
                is_default=is_default,
                extra_params=extra_params,
                capability_metadata=capability_metadata,
                default_options=default_options,
                capability_provenance=capability_provenance,
            ),
        )

    async def delete_tts_model(model_id: str) -> bool:
        return await tts_service.delete_model(model_id=model_id)

    async def get_rerank_model(model_id: str) -> AISourceModelDefinition | None:
        return await rerank_service.get_model(model_id=model_id)

    async def list_rerank_models(source_id: str) -> list[AISourceModelDefinition]:
        return list(await rerank_service.list_models(source_id=source_id))

    async def create_rerank_model(
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        capability_metadata: dict[str, object] | None,
        default_options: dict[str, object] | None,
        capability_provenance: dict[str, object] | None,
    ) -> AISourceModelDefinition:
        return await rerank_service.create_model(
            AIRerankModelCreateInput(
                source_id=source_id,
                model_identifier=model_identifier,
                display_name=display_name,
                enabled=enabled,
                is_default=is_default,
                extra_params=extra_params,
                capability_metadata=capability_metadata,
                default_options=default_options,
                capability_provenance=capability_provenance,
            ),
        )

    async def update_rerank_model(
        model_id: str,
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        capability_metadata: dict[str, object] | None,
        default_options: dict[str, object] | None,
        capability_provenance: dict[str, object] | None,
    ) -> AISourceModelDefinition | None:
        return await rerank_service.update_model(
            model_id=model_id,
            create_input=AIRerankModelCreateInput(
                source_id=source_id,
                model_identifier=model_identifier,
                display_name=display_name,
                enabled=enabled,
                is_default=is_default,
                extra_params=extra_params,
                capability_metadata=capability_metadata,
                default_options=default_options,
                capability_provenance=capability_provenance,
            ),
        )

    async def delete_rerank_model(model_id: str) -> bool:
        return await rerank_service.delete_model(model_id=model_id)

    return {
        "chat_completion": AICapabilityModelRegistryEntry(
            capability_type="chat_completion",
            get_model=get_chat_model,
            list_models=list_chat_models,
            create_model=create_chat_model,
            update_model=update_chat_model,
            delete_model=delete_chat_model,
        ),
        "embedding": AICapabilityModelRegistryEntry(
            capability_type="embedding",
            get_model=get_embedding_model,
            list_models=list_embedding_models,
            create_model=create_embedding_model,
            update_model=update_embedding_model,
            delete_model=delete_embedding_model,
        ),
        "speech_to_text": AICapabilityModelRegistryEntry(
            capability_type="speech_to_text",
            get_model=get_stt_model,
            list_models=list_stt_models,
            create_model=create_stt_model,
            update_model=update_stt_model,
            delete_model=delete_stt_model,
        ),
        "text_to_speech": AICapabilityModelRegistryEntry(
            capability_type="text_to_speech",
            get_model=get_tts_model,
            list_models=list_tts_models,
            create_model=create_tts_model,
            update_model=update_tts_model,
            delete_model=delete_tts_model,
        ),
        "rerank": AICapabilityModelRegistryEntry(
            capability_type="rerank",
            get_model=get_rerank_model,
            list_models=list_rerank_models,
            create_model=create_rerank_model,
            update_model=update_rerank_model,
            delete_model=delete_rerank_model,
        ),
    }


SOURCE_MODEL_CAPABILITY_REGISTRY = build_source_model_capability_registry()

SOURCE_MODEL_CAPABILITY_FALLBACK_ORDER: tuple["AISourceCapabilityType", ...] = (
    "chat_completion",
    "embedding",
    "speech_to_text",
    "text_to_speech",
    "rerank",
)

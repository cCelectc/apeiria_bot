"""Capability-oriented model service registry."""
# ruff: noqa: PLR0913, FBT001

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.ai.model.chat_model import (
    AIChatModelCreateInput,
    ai_chat_model_service,
)
from apeiria.ai.model.embedding_model import (
    AIEmbeddingModelCreateInput,
    ai_embedding_model_service,
)
from apeiria.ai.model.rerank_model import (
    AIRerankModelCreateInput,
    ai_rerank_model_service,
)
from apeiria.ai.model.source_models import AISourceModelDefinition
from apeiria.ai.model.stt_model import (
    AISTTModelCreateInput,
    ai_stt_model_service,
)
from apeiria.ai.model.tts_model import (
    AITTSModelCreateInput,
    ai_tts_model_service,
)

if TYPE_CHECKING:
    from apeiria.ai.model.sources import AISourceCapabilityType


ModelListFn = Callable[[str], Awaitable[list[AISourceModelDefinition]]]
ModelCreateFn = Callable[
    [str, str, str, bool, bool, dict[str, object]],
    Awaitable[AISourceModelDefinition],
]
ModelUpdateFn = Callable[
    [str, str, str, str, bool, bool, dict[str, object]],
    Awaitable[AISourceModelDefinition | None],
]
ModelDeleteFn = Callable[[str], Awaitable[bool]]


@dataclass(frozen=True)
class AICapabilityModelRegistryEntry:
    """One capability-specific source model manager entry."""

    capability_type: "AISourceCapabilityType"
    list_models: ModelListFn
    create_model: ModelCreateFn
    update_model: ModelUpdateFn
    delete_model: ModelDeleteFn


async def _list_chat_models(
    source_id: str,
) -> list[AISourceModelDefinition]:
    return list(await ai_chat_model_service.list_models(source_id=source_id))


async def _create_chat_model(
    source_id: str,
    model_identifier: str,
    display_name: str,
    enabled: bool,
    is_default: bool,
    extra_params: dict[str, object],
) -> AISourceModelDefinition:
    return await ai_chat_model_service.create_model(
        AIChatModelCreateInput(
            source_id=source_id,
            model_identifier=model_identifier,
            display_name=display_name,
            enabled=enabled,
            is_default=is_default,
            extra_params=extra_params,
        ),
    )


async def _update_chat_model(
    model_id: str,
    source_id: str,
    model_identifier: str,
    display_name: str,
    enabled: bool,
    is_default: bool,
    extra_params: dict[str, object],
) -> AISourceModelDefinition | None:
    return await ai_chat_model_service.update_model(
        model_id=model_id,
        create_input=AIChatModelCreateInput(
            source_id=source_id,
            model_identifier=model_identifier,
            display_name=display_name,
            enabled=enabled,
            is_default=is_default,
            extra_params=extra_params,
        ),
    )


async def _delete_chat_model(model_id: str) -> bool:
    return await ai_chat_model_service.delete_model(model_id=model_id)


async def _list_embedding_models(
    source_id: str,
) -> list[AISourceModelDefinition]:
    return list(await ai_embedding_model_service.list_models(source_id=source_id))


async def _create_embedding_model(
    source_id: str,
    model_identifier: str,
    display_name: str,
    enabled: bool,
    is_default: bool,
    extra_params: dict[str, object],
) -> AISourceModelDefinition:
    return await ai_embedding_model_service.create_model(
        AIEmbeddingModelCreateInput(
            source_id=source_id,
            model_identifier=model_identifier,
            display_name=display_name,
            enabled=enabled,
            is_default=is_default,
            extra_params=extra_params,
        ),
    )


async def _update_embedding_model(
    model_id: str,
    source_id: str,
    model_identifier: str,
    display_name: str,
    enabled: bool,
    is_default: bool,
    extra_params: dict[str, object],
) -> AISourceModelDefinition | None:
    return await ai_embedding_model_service.update_model(
        model_id=model_id,
        create_input=AIEmbeddingModelCreateInput(
            source_id=source_id,
            model_identifier=model_identifier,
            display_name=display_name,
            enabled=enabled,
            is_default=is_default,
            extra_params=extra_params,
        ),
    )


async def _delete_embedding_model(
    model_id: str,
) -> bool:
    return await ai_embedding_model_service.delete_model(model_id=model_id)


async def _list_stt_models(
    source_id: str,
) -> list[AISourceModelDefinition]:
    return list(await ai_stt_model_service.list_models(source_id=source_id))


async def _create_stt_model(
    source_id: str,
    model_identifier: str,
    display_name: str,
    enabled: bool,
    is_default: bool,
    extra_params: dict[str, object],
) -> AISourceModelDefinition:
    return await ai_stt_model_service.create_model(
        AISTTModelCreateInput(
            source_id=source_id,
            model_identifier=model_identifier,
            display_name=display_name,
            enabled=enabled,
            is_default=is_default,
            extra_params=extra_params,
        ),
    )


async def _update_stt_model(
    model_id: str,
    source_id: str,
    model_identifier: str,
    display_name: str,
    enabled: bool,
    is_default: bool,
    extra_params: dict[str, object],
) -> AISourceModelDefinition | None:
    return await ai_stt_model_service.update_model(
        model_id=model_id,
        create_input=AISTTModelCreateInput(
            source_id=source_id,
            model_identifier=model_identifier,
            display_name=display_name,
            enabled=enabled,
            is_default=is_default,
            extra_params=extra_params,
        ),
    )


async def _delete_stt_model(model_id: str) -> bool:
    return await ai_stt_model_service.delete_model(model_id=model_id)


async def _list_tts_models(
    source_id: str,
) -> list[AISourceModelDefinition]:
    return list(await ai_tts_model_service.list_models(source_id=source_id))


async def _create_tts_model(
    source_id: str,
    model_identifier: str,
    display_name: str,
    enabled: bool,
    is_default: bool,
    extra_params: dict[str, object],
) -> AISourceModelDefinition:
    return await ai_tts_model_service.create_model(
        AITTSModelCreateInput(
            source_id=source_id,
            model_identifier=model_identifier,
            display_name=display_name,
            enabled=enabled,
            is_default=is_default,
            extra_params=extra_params,
        ),
    )


async def _update_tts_model(
    model_id: str,
    source_id: str,
    model_identifier: str,
    display_name: str,
    enabled: bool,
    is_default: bool,
    extra_params: dict[str, object],
) -> AISourceModelDefinition | None:
    return await ai_tts_model_service.update_model(
        model_id=model_id,
        create_input=AITTSModelCreateInput(
            source_id=source_id,
            model_identifier=model_identifier,
            display_name=display_name,
            enabled=enabled,
            is_default=is_default,
            extra_params=extra_params,
        ),
    )


async def _delete_tts_model(model_id: str) -> bool:
    return await ai_tts_model_service.delete_model(model_id=model_id)


async def _list_rerank_models(
    source_id: str,
) -> list[AISourceModelDefinition]:
    return list(await ai_rerank_model_service.list_models(source_id=source_id))


async def _create_rerank_model(
    source_id: str,
    model_identifier: str,
    display_name: str,
    enabled: bool,
    is_default: bool,
    extra_params: dict[str, object],
) -> AISourceModelDefinition:
    return await ai_rerank_model_service.create_model(
        AIRerankModelCreateInput(
            source_id=source_id,
            model_identifier=model_identifier,
            display_name=display_name,
            enabled=enabled,
            is_default=is_default,
            extra_params=extra_params,
        ),
    )


async def _update_rerank_model(
    model_id: str,
    source_id: str,
    model_identifier: str,
    display_name: str,
    enabled: bool,
    is_default: bool,
    extra_params: dict[str, object],
) -> AISourceModelDefinition | None:
    return await ai_rerank_model_service.update_model(
        model_id=model_id,
        create_input=AIRerankModelCreateInput(
            source_id=source_id,
            model_identifier=model_identifier,
            display_name=display_name,
            enabled=enabled,
            is_default=is_default,
            extra_params=extra_params,
        ),
    )


async def _delete_rerank_model(
    model_id: str,
) -> bool:
    return await ai_rerank_model_service.delete_model(model_id=model_id)


SOURCE_MODEL_CAPABILITY_REGISTRY: dict[
    "AISourceCapabilityType", AICapabilityModelRegistryEntry
] = {
    "chat_completion": AICapabilityModelRegistryEntry(
        capability_type="chat_completion",
        list_models=_list_chat_models,
        create_model=_create_chat_model,
        update_model=_update_chat_model,
        delete_model=_delete_chat_model,
    ),
    "embedding": AICapabilityModelRegistryEntry(
        capability_type="embedding",
        list_models=_list_embedding_models,
        create_model=_create_embedding_model,
        update_model=_update_embedding_model,
        delete_model=_delete_embedding_model,
    ),
    "speech_to_text": AICapabilityModelRegistryEntry(
        capability_type="speech_to_text",
        list_models=_list_stt_models,
        create_model=_create_stt_model,
        update_model=_update_stt_model,
        delete_model=_delete_stt_model,
    ),
    "text_to_speech": AICapabilityModelRegistryEntry(
        capability_type="text_to_speech",
        list_models=_list_tts_models,
        create_model=_create_tts_model,
        update_model=_update_tts_model,
        delete_model=_delete_tts_model,
    ),
    "rerank": AICapabilityModelRegistryEntry(
        capability_type="rerank",
        list_models=_list_rerank_models,
        create_model=_create_rerank_model,
        update_model=_update_rerank_model,
        delete_model=_delete_rerank_model,
    ),
}

SOURCE_MODEL_CAPABILITY_FALLBACK_ORDER: tuple["AISourceCapabilityType", ...] = (
    "chat_completion",
    "embedding",
    "speech_to_text",
    "text_to_speech",
    "rerank",
)

"""Consolidated model boundary with lazy heavy-service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .catalog import (
    AIChatModelDefinition,
    AIEmbeddingModelDefinition,
    AIRerankModelDefinition,
    AISourceModelDefinition,
    AISpeechToTextModelDefinition,
    AITextToSpeechModelDefinition,
)
from .routing import (
    AIModelBindingSpec,
    AIModelBindingTarget,
    AIModelProfileDefinition,
    AIModelRouteQuery,
    AIModelTaskClass,
    AISelectedCapabilityModel,
    AISelectedModel,
    resolve_model_profile,
)
from .sources import (
    AISourceCapabilityType,
    AISourceClientType,
    AISourceDefinition,
    AISourcePresetDefinition,
    AISourcePresetType,
    UnsupportedAISourcePresetError,
    resolve_capability_type_for_preset,
    resolve_client_type_for_preset,
)

if TYPE_CHECKING:
    from .catalog.chat import (
        AIChatModelCreateInput,
        AIChatModelService,
        ai_chat_model_service,
    )
    from .catalog.embedding import (
        AIEmbeddingModelCreateInput,
        AIEmbeddingModelService,
        ai_embedding_model_service,
    )
    from .catalog.rerank import (
        AIRerankModelCreateInput,
        AIRerankModelService,
        ai_rerank_model_service,
    )
    from .catalog.stt import (
        AISTTModelCreateInput,
        AISTTModelService,
        ai_stt_model_service,
    )
    from .catalog.tts import (
        AITTSModelCreateInput,
        AITTSModelService,
        ai_tts_model_service,
    )
    from .routing.capability_selection import (
        AIModelCapabilitySelectionService,
        ai_model_capability_selection_service,
    )
    from .routing.profile import (
        AIModelProfileCreateInput,
        AIModelProfileService,
        ai_model_profile_service,
    )
    from .runtime.adapter import (
        AIModelAdapter,
        AIModelCatalogItem,
        AIModelEmbeddingRequest,
        AIModelEmbeddingResponse,
        AIModelGenerateRequest,
        AIModelGenerateResponse,
        AIModelMessage,
        AIModelMessageRole,
        AIModelRerankRequest,
        AIModelRerankResponse,
        AIModelSpeechRequest,
        AIModelSpeechResponse,
        AIModelToolCall,
        AIModelToolDefinition,
        AIModelTranscriptionRequest,
        AIModelTranscriptionResponse,
    )
    from .runtime.client import (
        AIModelClient,
        AIModelClientRegistry,
        UnknownAISourceError,
        ai_model_client,
    )
    from .runtime.factory import (
        UnsupportedAISourceClientTypeError,
        build_source_adapter,
    )
    from .runtime.gateway import ModelGateway, model_gateway
    from .runtime.service import AIModelFacade, ai_model_facade
    from .sources.service import (
        AISourceCreateInput,
        AISourceService,
        ai_source_service,
    )

__all__ = [
    "AIChatModelCreateInput",
    "AIChatModelDefinition",
    "AIChatModelService",
    "AIEmbeddingModelCreateInput",
    "AIEmbeddingModelDefinition",
    "AIEmbeddingModelService",
    "AIModelAdapter",
    "AIModelBindingSpec",
    "AIModelBindingTarget",
    "AIModelCapabilitySelectionService",
    "AIModelCatalogItem",
    "AIModelClient",
    "AIModelClientRegistry",
    "AIModelEmbeddingRequest",
    "AIModelEmbeddingResponse",
    "AIModelFacade",
    "AIModelGenerateRequest",
    "AIModelGenerateResponse",
    "AIModelMessage",
    "AIModelMessageRole",
    "AIModelProfileCreateInput",
    "AIModelProfileDefinition",
    "AIModelProfileService",
    "AIModelRerankRequest",
    "AIModelRerankResponse",
    "AIModelRouteQuery",
    "AIModelSpeechRequest",
    "AIModelSpeechResponse",
    "AIModelTaskClass",
    "AIModelToolCall",
    "AIModelToolDefinition",
    "AIModelTranscriptionRequest",
    "AIModelTranscriptionResponse",
    "AIRerankModelCreateInput",
    "AIRerankModelDefinition",
    "AIRerankModelService",
    "AISTTModelCreateInput",
    "AISTTModelService",
    "AISelectedCapabilityModel",
    "AISelectedModel",
    "AISourceCapabilityType",
    "AISourceClientType",
    "AISourceCreateInput",
    "AISourceDefinition",
    "AISourceModelDefinition",
    "AISourcePresetDefinition",
    "AISourcePresetType",
    "AISourceService",
    "AISpeechToTextModelDefinition",
    "AITTSModelCreateInput",
    "AITTSModelService",
    "AITextToSpeechModelDefinition",
    "ModelGateway",
    "UnknownAISourceError",
    "UnsupportedAISourceClientTypeError",
    "UnsupportedAISourcePresetError",
    "ai_chat_model_service",
    "ai_embedding_model_service",
    "ai_model_capability_selection_service",
    "ai_model_client",
    "ai_model_facade",
    "ai_model_profile_service",
    "ai_rerank_model_service",
    "ai_source_service",
    "ai_stt_model_service",
    "ai_tts_model_service",
    "build_source_adapter",
    "model_gateway",
    "resolve_capability_type_for_preset",
    "resolve_client_type_for_preset",
    "resolve_model_profile",
]

_LAZY_EXPORTS = {
    "AIChatModelCreateInput": ".catalog.chat",
    "AIChatModelService": ".catalog.chat",
    "AIModelClient": ".runtime.client",
    "AIModelClientRegistry": ".runtime.client",
    "AIModelCapabilitySelectionService": ".routing.capability_selection",
    "AIModelFacade": ".runtime.service",
    "AIRerankModelCreateInput": ".catalog.rerank",
    "AIRerankModelService": ".catalog.rerank",
    "AIEmbeddingModelCreateInput": ".catalog.embedding",
    "AIEmbeddingModelService": ".catalog.embedding",
    "AIModelGenerateRequest": ".runtime.adapter",
    "AIModelEmbeddingRequest": ".runtime.adapter",
    "AIModelEmbeddingResponse": ".runtime.adapter",
    "AIModelGenerateResponse": ".runtime.adapter",
    "AIModelMessage": ".runtime.adapter",
    "AIModelMessageRole": ".runtime.adapter",
    "AIModelRerankRequest": ".runtime.adapter",
    "AIModelRerankResponse": ".runtime.adapter",
    "AIModelSpeechRequest": ".runtime.adapter",
    "AIModelSpeechResponse": ".runtime.adapter",
    "AIModelProfileCreateInput": ".routing.profile",
    "AIModelProfileService": ".routing.profile",
    "AIModelTranscriptionRequest": ".runtime.adapter",
    "AIModelTranscriptionResponse": ".runtime.adapter",
    "AIModelToolCall": ".runtime.adapter",
    "AIModelToolDefinition": ".runtime.adapter",
    "AIModelAdapter": ".runtime.adapter",
    "AIModelCatalogItem": ".runtime.adapter",
    "ModelGateway": ".runtime.gateway",
    "AITTSModelCreateInput": ".catalog.tts",
    "AITTSModelService": ".catalog.tts",
    "AISTTModelCreateInput": ".catalog.stt",
    "AISTTModelService": ".catalog.stt",
    "AISourceCreateInput": ".sources.service",
    "AISourceService": ".sources.service",
    "UnknownAISourceError": ".runtime.client",
    "UnsupportedAISourceClientTypeError": ".runtime.factory",
    "ai_chat_model_service": ".catalog.chat",
    "ai_embedding_model_service": ".catalog.embedding",
    "ai_model_capability_selection_service": ".routing.capability_selection",
    "ai_model_client": ".runtime.client",
    "ai_model_facade": ".runtime.service",
    "ai_model_profile_service": ".routing.profile",
    "ai_rerank_model_service": ".catalog.rerank",
    "ai_source_service": ".sources.service",
    "ai_stt_model_service": ".catalog.stt",
    "ai_tts_model_service": ".catalog.tts",
    "build_source_adapter": ".runtime.factory",
    "model_gateway": ".runtime.gateway",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    return getattr(module, name)

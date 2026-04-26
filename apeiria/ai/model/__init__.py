"""Consolidated model boundary with lazy heavy-service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .bindings import AIModelBindingSpec, AIModelBindingTarget
from .chat_models import AIChatModelDefinition
from .models import AIModelProfileDefinition, AIModelRouteQuery, AIModelTaskClass
from .routing import resolve_model_profile
from .selection import AISelectedCapabilityModel, AISelectedModel
from .source_models import (
    AIEmbeddingModelDefinition,
    AIRerankModelDefinition,
    AISourceModelDefinition,
    AISpeechToTextModelDefinition,
    AITextToSpeechModelDefinition,
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
    from .adapter import (
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
    from .capability_selection import (
        AIModelCapabilitySelectionService,
        ai_model_capability_selection_service,
    )
    from .chat_model import (
        AIChatModelCreateInput,
        AIChatModelService,
        ai_chat_model_service,
    )
    from .client import (
        AIModelClient,
        AIModelClientRegistry,
        UnknownAISourceError,
        ai_model_client,
    )
    from .embedding_model import (
        AIEmbeddingModelCreateInput,
        AIEmbeddingModelService,
        ai_embedding_model_service,
    )
    from .factory import UnsupportedAISourceClientTypeError, build_source_adapter
    from .gateway import ModelGateway, model_gateway
    from .profile import (
        AIModelProfileCreateInput,
        AIModelProfileService,
        ai_model_profile_service,
    )
    from .rerank_model import (
        AIRerankModelCreateInput,
        AIRerankModelService,
        ai_rerank_model_service,
    )
    from .service import AIModelFacade, ai_model_facade
    from .source import (
        AISourceCreateInput,
        AISourceService,
        ai_source_service,
    )
    from .stt_model import (
        AISTTModelCreateInput,
        AISTTModelService,
        ai_stt_model_service,
    )
    from .tts_model import (
        AITTSModelCreateInput,
        AITTSModelService,
        ai_tts_model_service,
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
    "AIChatModelCreateInput": ".chat_model",
    "AIChatModelService": ".chat_model",
    "AIModelClient": ".client",
    "AIModelClientRegistry": ".client",
    "AIModelCapabilitySelectionService": ".capability_selection",
    "AIModelFacade": ".service",
    "AIRerankModelCreateInput": ".rerank_model",
    "AIRerankModelService": ".rerank_model",
    "AIEmbeddingModelCreateInput": ".embedding_model",
    "AIEmbeddingModelService": ".embedding_model",
    "AIModelGenerateRequest": ".adapter",
    "AIModelEmbeddingRequest": ".adapter",
    "AIModelEmbeddingResponse": ".adapter",
    "AIModelGenerateResponse": ".adapter",
    "AIModelMessage": ".adapter",
    "AIModelMessageRole": ".adapter",
    "AIModelRerankRequest": ".adapter",
    "AIModelRerankResponse": ".adapter",
    "AIModelSpeechRequest": ".adapter",
    "AIModelSpeechResponse": ".adapter",
    "AIModelProfileCreateInput": ".profile",
    "AIModelProfileService": ".profile",
    "AIModelTranscriptionRequest": ".adapter",
    "AIModelTranscriptionResponse": ".adapter",
    "AIModelToolCall": ".adapter",
    "AIModelToolDefinition": ".adapter",
    "AIModelAdapter": ".adapter",
    "AIModelCatalogItem": ".adapter",
    "ModelGateway": ".gateway",
    "AITTSModelCreateInput": ".tts_model",
    "AITTSModelService": ".tts_model",
    "AISTTModelCreateInput": ".stt_model",
    "AISTTModelService": ".stt_model",
    "AISourceCreateInput": ".source",
    "AISourceService": ".source",
    "UnknownAISourceError": ".client",
    "UnsupportedAISourceClientTypeError": ".factory",
    "ai_chat_model_service": ".chat_model",
    "ai_embedding_model_service": ".embedding_model",
    "ai_model_capability_selection_service": ".capability_selection",
    "ai_model_client": ".client",
    "ai_model_facade": ".service",
    "ai_model_profile_service": ".profile",
    "ai_rerank_model_service": ".rerank_model",
    "ai_source_service": ".source",
    "ai_stt_model_service": ".stt_model",
    "ai_tts_model_service": ".tts_model",
    "build_source_adapter": ".factory",
    "model_gateway": ".gateway",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    return getattr(module, name)

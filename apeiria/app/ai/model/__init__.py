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
)

if TYPE_CHECKING:
    from .adapter import (
        AIModelAdapter,
        AIModelCatalogItem,
        AIModelEmbeddingRequest,
        AIModelEmbeddingResponse,
        AIModelGenerateRequest,
        AIModelGenerateResponse,
        AIModelRerankRequest,
        AIModelRerankResponse,
        AIModelSpeechRequest,
        AIModelSpeechResponse,
        AIModelTranscriptionRequest,
        AIModelTranscriptionResponse,
    )
    from .chat_model_service import (
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
    from .capability_selection_service import (
        AIModelCapabilitySelectionService,
        ai_model_capability_selection_service,
    )
    from .embedding_model_service import (
        AIEmbeddingModelCreateInput,
        AIEmbeddingModelService,
        ai_embedding_model_service,
    )
    from .factory import UnsupportedAISourceClientTypeError, build_source_adapter
    from .profile_service import (
        AIModelProfileCreateInput,
        AIModelProfileService,
        ai_model_profile_service,
    )
    from .rerank_model_service import (
        AIRerankModelCreateInput,
        AIRerankModelService,
        ai_rerank_model_service,
    )
    from .service import AIModelFacade, ai_model_facade
    from .source_service import (
        AISourceCreateInput,
        AISourceService,
        ai_source_service,
    )
    from .stt_model_service import (
        AISTTModelCreateInput,
        AISTTModelService,
        ai_stt_model_service,
    )
    from .tts_model_service import (
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
    "AIModelProfileCreateInput",
    "AIModelProfileDefinition",
    "AIModelProfileService",
    "AIModelRerankRequest",
    "AIModelRerankResponse",
    "AIModelRouteQuery",
    "AIModelSpeechRequest",
    "AIModelSpeechResponse",
    "AIModelTaskClass",
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
    "UnknownAISourceError",
    "UnsupportedAISourceClientTypeError",
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
    "resolve_model_profile",
]

_LAZY_EXPORTS = {
    "AIChatModelCreateInput": ".chat_model_service",
    "AIChatModelService": ".chat_model_service",
    "AIModelClient": ".client",
    "AIModelClientRegistry": ".client",
    "AIModelCapabilitySelectionService": ".capability_selection_service",
    "AIModelFacade": ".service",
    "AIRerankModelCreateInput": ".rerank_model_service",
    "AIRerankModelService": ".rerank_model_service",
    "AIEmbeddingModelCreateInput": ".embedding_model_service",
    "AIEmbeddingModelService": ".embedding_model_service",
    "AIModelGenerateRequest": ".adapter",
    "AIModelEmbeddingRequest": ".adapter",
    "AIModelEmbeddingResponse": ".adapter",
    "AIModelGenerateResponse": ".adapter",
    "AIModelRerankRequest": ".adapter",
    "AIModelRerankResponse": ".adapter",
    "AIModelSpeechRequest": ".adapter",
    "AIModelSpeechResponse": ".adapter",
    "AIModelProfileCreateInput": ".profile_service",
    "AIModelProfileService": ".profile_service",
    "AIModelTranscriptionRequest": ".adapter",
    "AIModelTranscriptionResponse": ".adapter",
    "AIModelAdapter": ".adapter",
    "AIModelCatalogItem": ".adapter",
    "AITTSModelCreateInput": ".tts_model_service",
    "AITTSModelService": ".tts_model_service",
    "AISTTModelCreateInput": ".stt_model_service",
    "AISTTModelService": ".stt_model_service",
    "AISourceCreateInput": ".source_service",
    "AISourceService": ".source_service",
    "UnknownAISourceError": ".client",
    "UnsupportedAISourceClientTypeError": ".factory",
    "ai_chat_model_service": ".chat_model_service",
    "ai_embedding_model_service": ".embedding_model_service",
    "ai_model_capability_selection_service": ".capability_selection_service",
    "ai_model_client": ".client",
    "ai_model_facade": ".service",
    "ai_model_profile_service": ".profile_service",
    "ai_rerank_model_service": ".rerank_model_service",
    "ai_source_service": ".source_service",
    "ai_stt_model_service": ".stt_model_service",
    "ai_tts_model_service": ".tts_model_service",
    "build_source_adapter": ".factory",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value

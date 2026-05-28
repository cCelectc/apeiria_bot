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
    AIModelAttemptPlan,
    AIModelBindingSpec,
    AIModelBindingTarget,
    AIModelProfileDefinition,
    AIModelRouteAlgorithm,
    AIModelRouteBindingSpec,
    AIModelRouteDefinition,
    AIModelRouteMemberDefinition,
    AIModelRouteMode,
    AIModelRouteQuery,
    AIModelRouteScopeType,
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
    resolve_adapter_kind_for_client_type,
    resolve_adapter_kind_for_preset,
    resolve_capability_type_for_preset,
    resolve_client_type_for_preset,
)

if TYPE_CHECKING:
    from .catalog.chat import (
        AIChatModelCreateInput,
        AIChatModelService,
    )
    from .catalog.embedding import (
        AIEmbeddingModelCreateInput,
        AIEmbeddingModelService,
    )
    from .catalog.rerank import (
        AIRerankModelCreateInput,
        AIRerankModelService,
    )
    from .catalog.stt import (
        AISTTModelCreateInput,
        AISTTModelService,
    )
    from .catalog.tts import (
        AITTSModelCreateInput,
        AITTSModelService,
    )
    from .routing.capability_selection import (
        AIModelCapabilitySelectionService,
    )
    from .routing.profile import (
        AIModelProfileCreateInput,
        AIModelProfileService,
    )
    from .routing.routes import (
        AIModelRouteBindingCreateInput,
        AIModelRouteCreateInput,
        AIModelRouteMemberCreateInput,
        AIModelRouteService,
    )
    from .runtime.adapter import (
        AIModelAdapter,
        AIModelCatalogItem,
        AIModelContentPart,
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
        AIModelStreamEvent,
        AIModelStreamRequest,
        AIModelToolCall,
        AIModelToolDefinition,
        AIModelTranscriptionRequest,
        AIModelTranscriptionResponse,
    )
    from .runtime.client import (
        AIModelClient,
        AIModelClientRegistry,
        UnknownAISourceError,
    )
    from .runtime.factory import (
        UnsupportedAISourceClientTypeError,
        build_source_adapter,
    )
    from .runtime.service import ModelInvoker
    from .sources.service import AISourceCreateInput, AISourceService

__all__ = [
    "AIChatModelCreateInput",
    "AIChatModelDefinition",
    "AIChatModelService",
    "AIEmbeddingModelCreateInput",
    "AIEmbeddingModelDefinition",
    "AIEmbeddingModelService",
    "AIModelAdapter",
    "AIModelAttemptPlan",
    "AIModelBindingSpec",
    "AIModelBindingTarget",
    "AIModelCapabilitySelectionService",
    "AIModelCatalogItem",
    "AIModelClient",
    "AIModelClientRegistry",
    "AIModelContentPart",
    "AIModelEmbeddingRequest",
    "AIModelEmbeddingResponse",
    "AIModelGenerateRequest",
    "AIModelGenerateResponse",
    "AIModelMessage",
    "AIModelMessageRole",
    "AIModelProfileCreateInput",
    "AIModelProfileDefinition",
    "AIModelProfileService",
    "AIModelRerankRequest",
    "AIModelRerankResponse",
    "AIModelRouteAlgorithm",
    "AIModelRouteBindingCreateInput",
    "AIModelRouteBindingSpec",
    "AIModelRouteCreateInput",
    "AIModelRouteDefinition",
    "AIModelRouteMemberCreateInput",
    "AIModelRouteMemberDefinition",
    "AIModelRouteMode",
    "AIModelRouteQuery",
    "AIModelRouteScopeType",
    "AIModelRouteService",
    "AIModelSpeechRequest",
    "AIModelSpeechResponse",
    "AIModelStreamEvent",
    "AIModelStreamRequest",
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
    "ModelInvoker",
    "UnknownAISourceError",
    "UnsupportedAISourceClientTypeError",
    "UnsupportedAISourcePresetError",
    "build_source_adapter",
    "resolve_adapter_kind_for_client_type",
    "resolve_adapter_kind_for_preset",
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
    "AIRerankModelCreateInput": ".catalog.rerank",
    "AIRerankModelService": ".catalog.rerank",
    "AIEmbeddingModelCreateInput": ".catalog.embedding",
    "AIEmbeddingModelService": ".catalog.embedding",
    "AIModelGenerateRequest": ".runtime.adapter",
    "AIModelEmbeddingRequest": ".runtime.adapter",
    "AIModelEmbeddingResponse": ".runtime.adapter",
    "AIModelGenerateResponse": ".runtime.adapter",
    "AIModelContentPart": ".runtime.adapter",
    "AIModelMessage": ".runtime.adapter",
    "AIModelMessageRole": ".runtime.adapter",
    "AIModelRerankRequest": ".runtime.adapter",
    "AIModelRerankResponse": ".runtime.adapter",
    "AIModelSpeechRequest": ".runtime.adapter",
    "AIModelSpeechResponse": ".runtime.adapter",
    "AIModelStreamEvent": ".runtime.adapter",
    "AIModelStreamRequest": ".runtime.adapter",
    "AIModelProfileCreateInput": ".routing.profile",
    "AIModelProfileService": ".routing.profile",
    "AIModelRouteBindingCreateInput": ".routing.routes",
    "AIModelRouteCreateInput": ".routing.routes",
    "AIModelRouteMemberCreateInput": ".routing.routes",
    "AIModelRouteService": ".routing.routes",
    "AIModelTranscriptionRequest": ".runtime.adapter",
    "AIModelTranscriptionResponse": ".runtime.adapter",
    "AIModelToolCall": ".runtime.adapter",
    "AIModelToolDefinition": ".runtime.adapter",
    "AIModelAdapter": ".runtime.adapter",
    "AIModelCatalogItem": ".runtime.adapter",
    "ModelInvoker": ".runtime.service",
    "AITTSModelCreateInput": ".catalog.tts",
    "AITTSModelService": ".catalog.tts",
    "AISTTModelCreateInput": ".catalog.stt",
    "AISTTModelService": ".catalog.stt",
    "AISourceCreateInput": ".sources.service",
    "AISourceService": ".sources.service",
    "UnknownAISourceError": ".runtime.client",
    "UnsupportedAISourceClientTypeError": ".runtime.factory",
    "build_source_adapter": ".runtime.factory",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    return getattr(module, name)

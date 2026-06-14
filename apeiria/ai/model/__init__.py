"""Consolidated model boundary."""

from __future__ import annotations

from .catalog import (
    AIChatModelDefinition,
    AIEmbeddingModelDefinition,
    AIRerankModelDefinition,
    AISourceModelDefinition,
    AISpeechToTextModelDefinition,
    AITextToSpeechModelDefinition,
)
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

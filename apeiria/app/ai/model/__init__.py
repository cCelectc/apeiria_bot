"""Consolidated model boundary with lazy heavy-service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .bindings import AIModelBindingSpec, AIModelBindingTarget
from .chat_models import AIChatModelDefinition
from .models import AIModelProfileDefinition, AIModelRouteQuery, AIModelTaskClass
from .routing import resolve_model_profile
from .selection import AISelectedModel
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
        AIModelGenerateRequest,
        AIModelGenerateResponse,
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
    from .factory import UnsupportedAISourceClientTypeError, build_source_adapter
    from .profile_service import (
        AIModelProfileCreateInput,
        AIModelProfileService,
        ai_model_profile_service,
    )
    from .service import AIModelFacade, ai_model_facade
    from .source_service import (
        AISourceCreateInput,
        AISourceService,
        ai_source_service,
    )

__all__ = [
    "AIChatModelCreateInput",
    "AIChatModelDefinition",
    "AIChatModelService",
    "AIModelAdapter",
    "AIModelBindingSpec",
    "AIModelBindingTarget",
    "AIModelCatalogItem",
    "AIModelClient",
    "AIModelClientRegistry",
    "AIModelFacade",
    "AIModelGenerateRequest",
    "AIModelGenerateResponse",
    "AIModelProfileCreateInput",
    "AIModelProfileDefinition",
    "AIModelProfileService",
    "AIModelRouteQuery",
    "AIModelTaskClass",
    "AISelectedModel",
    "AISourceCapabilityType",
    "AISourceClientType",
    "AISourceCreateInput",
    "AISourceDefinition",
    "AISourcePresetDefinition",
    "AISourcePresetType",
    "AISourceService",
    "UnknownAISourceError",
    "UnsupportedAISourceClientTypeError",
    "ai_chat_model_service",
    "ai_model_client",
    "ai_model_facade",
    "ai_model_profile_service",
    "ai_source_service",
    "build_source_adapter",
    "resolve_model_profile",
]

_LAZY_EXPORTS = {
    "AIChatModelCreateInput": ".chat_model_service",
    "AIChatModelService": ".chat_model_service",
    "AIModelClient": ".client",
    "AIModelClientRegistry": ".client",
    "AIModelFacade": ".service",
    "AIModelGenerateRequest": ".adapter",
    "AIModelGenerateResponse": ".adapter",
    "AIModelProfileCreateInput": ".profile_service",
    "AIModelProfileService": ".profile_service",
    "AIModelAdapter": ".adapter",
    "AIModelCatalogItem": ".adapter",
    "AISourceCreateInput": ".source_service",
    "AISourceService": ".source_service",
    "UnknownAISourceError": ".client",
    "UnsupportedAISourceClientTypeError": ".factory",
    "ai_chat_model_service": ".chat_model_service",
    "ai_model_client": ".client",
    "ai_model_facade": ".service",
    "ai_model_profile_service": ".profile_service",
    "ai_source_service": ".source_service",
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

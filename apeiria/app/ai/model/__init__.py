"""Consolidated model boundary with lazy heavy-service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .bindings import AIModelBindingSpec, AIModelBindingTarget
from .models import AIModelProfileDefinition, AIModelRouteQuery, AIModelTaskClass
from .providers import AIProviderDefinition, AIProviderType
from .routing import resolve_model_profile
from .selection import AISelectedModel, select_provider_for_profile

if TYPE_CHECKING:
    from .client import (
        AIModelClient,
        AIModelClientRegistry,
        UnknownAIProviderError,
        ai_model_client,
    )
    from .factory import UnsupportedAIProviderTypeError, build_provider_adapter
    from .profile_service import (
        AIModelProfileCreateInput,
        AIModelProfileService,
        ai_model_profile_service,
    )
    from .provider import (
        AIModelGenerateRequest,
        AIModelGenerateResponse,
        AIModelProvider,
        AIProviderModelItem,
    )
    from .provider_service import (
        AIProviderCreateInput,
        AIProviderService,
        ai_provider_service,
    )
    from .service import AIModelFacade, ai_model_facade

__all__ = [
    "AIModelBindingSpec",
    "AIModelBindingTarget",
    "AIModelClient",
    "AIModelClientRegistry",
    "AIModelFacade",
    "AIModelGenerateRequest",
    "AIModelGenerateResponse",
    "AIModelProfileCreateInput",
    "AIModelProfileDefinition",
    "AIModelProfileService",
    "AIModelProvider",
    "AIModelRouteQuery",
    "AIModelTaskClass",
    "AIProviderCreateInput",
    "AIProviderDefinition",
    "AIProviderModelItem",
    "AIProviderService",
    "AIProviderType",
    "AISelectedModel",
    "UnknownAIProviderError",
    "UnsupportedAIProviderTypeError",
    "ai_model_client",
    "ai_model_facade",
    "ai_model_profile_service",
    "ai_provider_service",
    "build_provider_adapter",
    "resolve_model_profile",
    "select_provider_for_profile",
]

_LAZY_EXPORTS = {
    "AIModelClient": ".client",
    "AIModelClientRegistry": ".client",
    "UnknownAIProviderError": ".client",
    "ai_model_client": ".client",
    "UnsupportedAIProviderTypeError": ".factory",
    "build_provider_adapter": ".factory",
    "AIModelProfileCreateInput": ".profile_service",
    "AIModelProfileService": ".profile_service",
    "ai_model_profile_service": ".profile_service",
    "AIModelGenerateRequest": ".provider",
    "AIModelGenerateResponse": ".provider",
    "AIModelProvider": ".provider",
    "AIProviderModelItem": ".provider",
    "AIProviderCreateInput": ".provider_service",
    "AIProviderService": ".provider_service",
    "ai_provider_service": ".provider_service",
    "AIModelFacade": ".service",
    "ai_model_facade": ".service",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value

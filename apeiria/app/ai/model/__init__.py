"""Consolidated model boundary over legacy models/providers packages."""

from .bindings import AIModelBindingSpec, AIModelBindingTarget
from .client import (
    AIModelClient,
    AIModelClientRegistry,
    UnknownAIProviderError,
    ai_model_client,
)
from .factory import UnsupportedAIProviderTypeError, build_provider_adapter
from .models import (
    AIModelProfileDefinition,
    AIModelRouteQuery,
    AIModelTaskClass,
)
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
from .providers import AIProviderDefinition, AIProviderType
from .routing import resolve_model_profile
from .selection import AISelectedModel, select_provider_for_profile
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

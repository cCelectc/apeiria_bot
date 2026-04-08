"""Multi-model routing domain for the Apeiria AI plugin rewrite."""

from .client import (
    AIModelClient,
    AIModelClientRegistry,
    UnknownAIProviderError,
    ai_model_client,
)
from .factory import UnsupportedAIProviderTypeError, build_provider_adapter
from .models import AIModelProfileDefinition, AIModelRouteQuery, AIModelTaskClass
from .provider import (
    AIModelGenerateRequest,
    AIModelGenerateResponse,
    AIModelProvider,
    AIProviderModelItem,
)
from .routing import resolve_model_profile

__all__ = [
    "AIModelClient",
    "AIModelClientRegistry",
    "AIModelGenerateRequest",
    "AIModelGenerateResponse",
    "AIModelProfileDefinition",
    "AIModelProvider",
    "AIModelRouteQuery",
    "AIModelTaskClass",
    "AIProviderModelItem",
    "UnknownAIProviderError",
    "UnsupportedAIProviderTypeError",
    "ai_model_client",
    "build_provider_adapter",
    "resolve_model_profile",
]

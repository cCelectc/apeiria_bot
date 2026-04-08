"""Provider client registry and dispatch facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.models.provider import (
        AIModelGenerateRequest,
        AIModelGenerateResponse,
        AIModelProvider,
        AIProviderModelItem,
    )


class UnknownAIProviderError(RuntimeError):
    """Raised when a requested AI provider is not registered."""

    def __init__(self, provider_name: str) -> None:
        super().__init__(f"provider '{provider_name}' is not registered")


@dataclass
class AIModelClientRegistry:
    """In-memory provider registry for AI model execution."""

    providers: dict[str, "AIModelProvider"]

    def register(self, provider_name: str, provider: "AIModelProvider") -> None:
        self.providers[provider_name] = provider

    def get(self, provider_name: str) -> "AIModelProvider | None":
        return self.providers.get(provider_name)


class AIModelClient:
    """Thin dispatch facade over registered provider adapters."""

    def __init__(self, registry: AIModelClientRegistry | None = None) -> None:
        self.registry = registry or AIModelClientRegistry(providers={})

    async def generate_text(
        self,
        request: "AIModelGenerateRequest",
    ) -> "AIModelGenerateResponse":
        provider = self.registry.get(request.provider_id)
        if provider is None:
            raise UnknownAIProviderError(request.provider_id)
        return await provider.generate_text(request)

    async def list_models(
        self,
        *,
        provider_id: str,
        api_key: str | None = None,
    ) -> list["AIProviderModelItem"]:
        provider = self.registry.get(provider_id)
        if provider is None:
            raise UnknownAIProviderError(provider_id)
        return await provider.list_models(api_key=api_key)


ai_model_client = AIModelClient()

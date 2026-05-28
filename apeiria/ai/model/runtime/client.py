"""Source adapter registry and dispatcher."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from apeiria.ai.model.runtime.adapter import (
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
        AIModelStreamEvent,
        AIModelStreamRequest,
        AIModelTranscriptionRequest,
        AIModelTranscriptionResponse,
    )


class UnknownAISourceError(RuntimeError):
    """Raised when a requested AI source adapter is not registered."""

    def __init__(self, source_id: str) -> None:
        super().__init__(f"source '{source_id}' is not registered")


@dataclass
class AIModelClientRegistry:
    """In-memory source adapter registry for AI model execution."""

    adapters: dict[str, "AIModelAdapter"]

    def register(self, source_id: str, adapter: "AIModelAdapter") -> None:
        self.adapters[source_id] = adapter

    def get(self, source_id: str) -> "AIModelAdapter | None":
        return self.adapters.get(source_id)


class AIModelClient:
    """Thin dispatcher over registered source adapters."""

    def __init__(self, registry: AIModelClientRegistry | None = None) -> None:
        self.registry = registry or AIModelClientRegistry(adapters={})

    async def generate_text(
        self,
        request: "AIModelGenerateRequest",
    ) -> "AIModelGenerateResponse":
        adapter = self.registry.get(request.source_id)
        if adapter is None:
            raise UnknownAISourceError(request.source_id)
        return await adapter.generate_text(request)

    def stream_text(
        self,
        request: "AIModelStreamRequest",
    ) -> "AsyncIterator[AIModelStreamEvent]":
        adapter = self.registry.get(request.source_id)
        if adapter is None:
            raise UnknownAISourceError(request.source_id)
        return adapter.stream_text(request)

    async def list_models(
        self,
        *,
        source_id: str,
        api_key: str | None = None,
    ) -> list["AIModelCatalogItem"]:
        adapter = self.registry.get(source_id)
        if adapter is None:
            raise UnknownAISourceError(source_id)
        return await adapter.list_models(api_key=api_key)

    async def embed_texts(
        self,
        request: "AIModelEmbeddingRequest",
    ) -> "AIModelEmbeddingResponse":
        adapter = self.registry.get(request.source_id)
        if adapter is None:
            raise UnknownAISourceError(request.source_id)
        return await adapter.embed_texts(request)

    async def transcribe_audio(
        self,
        request: "AIModelTranscriptionRequest",
    ) -> "AIModelTranscriptionResponse":
        adapter = self.registry.get(request.source_id)
        if adapter is None:
            raise UnknownAISourceError(request.source_id)
        return await adapter.transcribe_audio(request)

    async def synthesize_speech(
        self,
        request: "AIModelSpeechRequest",
    ) -> "AIModelSpeechResponse":
        adapter = self.registry.get(request.source_id)
        if adapter is None:
            raise UnknownAISourceError(request.source_id)
        return await adapter.synthesize_speech(request)

    async def rerank_documents(
        self,
        request: "AIModelRerankRequest",
    ) -> "AIModelRerankResponse":
        adapter = self.registry.get(request.source_id)
        if adapter is None:
            raise UnknownAISourceError(request.source_id)
        return await adapter.rerank_documents(request)

"""Canonical production composition for AI model-domain services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.model.catalog.chat import AIChatModelService
from apeiria.ai.model.catalog.embedding import AIEmbeddingModelService
from apeiria.ai.model.catalog.registry import (
    AICapabilityModelRegistryEntry,
    build_source_model_capability_registry,
)
from apeiria.ai.model.catalog.rerank import AIRerankModelService
from apeiria.ai.model.catalog.stt import AISTTModelService
from apeiria.ai.model.catalog.tts import AITTSModelService
from apeiria.ai.model.routing.capability_selection import (
    AIModelCapabilitySelectionService,
)
from apeiria.ai.model.routing.profile import AIModelProfileService
from apeiria.ai.model.routing.routes import AIModelRouteService
from apeiria.ai.model.runtime.client import AIModelClient
from apeiria.ai.model.runtime.service import ModelInvoker
from apeiria.ai.model.sources.service import AISourceService

if TYPE_CHECKING:
    from apeiria.ai.model.sources.models import AISourceCapabilityType


class AIModelWiring:
    """Lazy app-layer composition for model source/catalog/routing/runtime."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        source_service: AISourceService | None = None,
        chat_model_service: AIChatModelService | None = None,
        embedding_model_service: AIEmbeddingModelService | None = None,
        rerank_model_service: AIRerankModelService | None = None,
        stt_model_service: AISTTModelService | None = None,
        tts_model_service: AITTSModelService | None = None,
        capability_registry: (
            dict["AISourceCapabilityType", AICapabilityModelRegistryEntry] | None
        ) = None,
        profile_service: AIModelProfileService | None = None,
        route_service: AIModelRouteService | None = None,
        capability_selection_service: AIModelCapabilitySelectionService | None = None,
        client: AIModelClient | None = None,
        invoker: ModelInvoker | None = None,
    ) -> None:
        self._source_service = source_service
        self._chat_model_service = chat_model_service
        self._embedding_model_service = embedding_model_service
        self._rerank_model_service = rerank_model_service
        self._stt_model_service = stt_model_service
        self._tts_model_service = tts_model_service
        self._capability_registry = capability_registry
        self._profile_service = profile_service
        self._route_service = route_service
        self._capability_selection_service = capability_selection_service
        self._client = client
        self._invoker = invoker

    @property
    def source_service(self) -> AISourceService:
        if self._source_service is None:
            self._source_service = AISourceService()
        return self._source_service

    @property
    def chat_model_service(self) -> AIChatModelService:
        if self._chat_model_service is None:
            self._chat_model_service = AIChatModelService()
        return self._chat_model_service

    @property
    def embedding_model_service(self) -> AIEmbeddingModelService:
        if self._embedding_model_service is None:
            self._embedding_model_service = AIEmbeddingModelService()
        return self._embedding_model_service

    @property
    def rerank_model_service(self) -> AIRerankModelService:
        if self._rerank_model_service is None:
            self._rerank_model_service = AIRerankModelService()
        return self._rerank_model_service

    @property
    def stt_model_service(self) -> AISTTModelService:
        if self._stt_model_service is None:
            self._stt_model_service = AISTTModelService()
        return self._stt_model_service

    @property
    def tts_model_service(self) -> AITTSModelService:
        if self._tts_model_service is None:
            self._tts_model_service = AITTSModelService()
        return self._tts_model_service

    @property
    def capability_registry(
        self,
    ) -> dict["AISourceCapabilityType", AICapabilityModelRegistryEntry]:
        if self._capability_registry is None:
            self._capability_registry = build_source_model_capability_registry(
                chat_model_service=self.chat_model_service,
                embedding_model_service=self.embedding_model_service,
                rerank_model_service=self.rerank_model_service,
                stt_model_service=self.stt_model_service,
                tts_model_service=self.tts_model_service,
            )
        return self._capability_registry

    @property
    def profile_service(self) -> AIModelProfileService:
        if self._profile_service is None:
            self._profile_service = AIModelProfileService(
                source_service=self.source_service,
                chat_model_service=self.chat_model_service,
            )
        return self._profile_service

    @property
    def route_service(self) -> AIModelRouteService:
        if self._route_service is None:
            self._route_service = AIModelRouteService(
                source_service=self.source_service,
                chat_model_service=self.chat_model_service,
                profile_service=self.profile_service,
            )
        return self._route_service

    @property
    def capability_selection_service(self) -> AIModelCapabilitySelectionService:
        if self._capability_selection_service is None:
            self._capability_selection_service = AIModelCapabilitySelectionService(
                source_service=self.source_service,
                capability_registry=self.capability_registry,
            )
        return self._capability_selection_service

    @property
    def client(self) -> AIModelClient:
        if self._client is None:
            self._client = AIModelClient()
        return self._client

    @property
    def invoker(self) -> ModelInvoker:
        if self._invoker is None:
            self._invoker = ModelInvoker(
                client=self.client,
                source_service=self.source_service,
            )
        return self._invoker


__all__ = ["AIModelWiring"]

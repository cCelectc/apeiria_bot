"""Model facade over source, profile, and adapter services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from apeiria.app.ai.model.adapter import (
    AIModelEmbeddingRequest,
    AIModelGenerateRequest,
    AIModelRerankRequest,
    AIModelSpeechRequest,
    AIModelTranscriptionRequest,
)
from apeiria.app.ai.model.capability_selection_service import (
    ai_model_capability_selection_service,
)
from apeiria.app.ai.model.client import ai_model_client
from apeiria.app.ai.model.factory import build_source_adapter
from apeiria.app.ai.model.profile_service import ai_model_profile_service
from apeiria.app.ai.model.source_service import ai_source_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.model.adapter import (
        AIModelCatalogItem,
        AIModelEmbeddingResponse,
        AIModelGenerateResponse,
        AIModelRerankResponse,
        AIModelSpeechResponse,
        AIModelToolDefinition,
        AIModelTranscriptionResponse,
    )
    from apeiria.app.ai.model.bindings import AIModelBindingSpec, AIModelBindingTarget
    from apeiria.app.ai.model.models import (
        AIModelProfileDefinition,
        AIModelRouteQuery,
    )
    from apeiria.app.ai.model.selection import (
        AISelectedCapabilityModel,
        AISelectedModel,
    )
    from apeiria.app.ai.model.sources import AISourceCapabilityType, AISourceDefinition


class AIModelFacade:
    """Unified model boundary used by runtime and admin surfaces."""

    async def list_profiles(
        self,
        session: "AsyncSession",
    ) -> list["AIModelProfileDefinition"]:
        return await ai_model_profile_service.list_profiles(session)

    async def list_bindings(
        self,
        session: "AsyncSession",
    ) -> list["AIModelBindingSpec"]:
        return await ai_model_profile_service.list_bindings(session)

    async def list_source_models(
        self,
        *,
        source: "AISourceDefinition",
        api_key: str,
    ) -> list["AIModelCatalogItem"]:
        self._register_source(source, api_key=api_key)
        return await ai_model_client.list_models(
            source_id=source.source_id,
            api_key=api_key,
        )

    async def select_model(
        self,
        session: "AsyncSession",
        query: "AIModelRouteQuery | None" = None,
        *,
        target: "AIModelBindingTarget | None" = None,
    ) -> "AISelectedModel | None":
        return await ai_model_profile_service.select_model(
            session,
            query=query,
            target=target,
        )

    async def select_capability_model(
        self,
        session: "AsyncSession",
        *,
        capability_type: "AISourceCapabilityType",
        preferred_source_id: str | None = None,
    ) -> "AISelectedCapabilityModel | None":
        return await ai_model_capability_selection_service.select_default_model(
            session,
            capability_type=capability_type,
            preferred_source_id=preferred_source_id,
        )

    async def generate_text(
        self,
        selected: "AISelectedModel",
        *,
        prompt: str,
        tools: tuple["AIModelToolDefinition", ...] = (),
    ) -> "AIModelGenerateResponse | None":
        api_key = ai_source_service.get_source_api_key(selected.source)
        model_name = self.resolve_model_name(selected)
        if not api_key or not model_name:
            return None

        self._register_source(selected.source, api_key=api_key)
        return await ai_model_client.generate_text(
            AIModelGenerateRequest(
                source_id=selected.source.source_id,
                model_name=model_name,
                prompt=prompt,
                tools=tools,
            )
        )

    async def generate_text_for_source(
        self,
        *,
        source: "AISourceDefinition",
        api_key: str,
        model_name: str,
        prompt: str,
        max_tokens: int | None = None,
    ) -> "AIModelGenerateResponse":
        self._register_source(source, api_key=api_key)
        return await ai_model_client.generate_text(
            AIModelGenerateRequest(
                source_id=source.source_id,
                model_name=model_name,
                prompt=prompt,
                max_tokens=max_tokens,
            )
        )

    async def embed_texts_for_source(
        self,
        *,
        source: "AISourceDefinition",
        api_key: str,
        model_name: str,
        texts: tuple[str, ...],
    ) -> "AIModelEmbeddingResponse":
        self._register_source(source, api_key=api_key)
        return await ai_model_client.embed_texts(
            AIModelEmbeddingRequest(
                source_id=source.source_id,
                model_name=model_name,
                texts=texts,
            )
        )

    async def transcribe_audio_for_source(  # noqa: PLR0913
        self,
        *,
        source: "AISourceDefinition",
        api_key: str,
        model_name: str,
        audio_bytes: bytes,
        file_name: str = "sample.wav",
        mime_type: str = "audio/wav",
        language: str | None = None,
    ) -> "AIModelTranscriptionResponse":
        self._register_source(source, api_key=api_key)
        return await ai_model_client.transcribe_audio(
            AIModelTranscriptionRequest(
                source_id=source.source_id,
                model_name=model_name,
                audio_bytes=audio_bytes,
                file_name=file_name,
                mime_type=mime_type,
                language=language,
            )
        )

    async def synthesize_speech_for_source(  # noqa: PLR0913
        self,
        *,
        source: "AISourceDefinition",
        api_key: str,
        model_name: str,
        text: str,
        voice: str = "alloy",
        response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "wav",
    ) -> "AIModelSpeechResponse":
        self._register_source(source, api_key=api_key)
        return await ai_model_client.synthesize_speech(
            AIModelSpeechRequest(
                source_id=source.source_id,
                model_name=model_name,
                text=text,
                voice=voice,
                response_format=response_format,
            )
        )

    async def rerank_documents_for_source(  # noqa: PLR0913
        self,
        *,
        source: "AISourceDefinition",
        api_key: str,
        model_name: str,
        query: str,
        documents: tuple[str, ...],
        top_n: int = 3,
    ) -> "AIModelRerankResponse":
        self._register_source(source, api_key=api_key)
        return await ai_model_client.rerank_documents(
            AIModelRerankRequest(
                source_id=source.source_id,
                model_name=model_name,
                query=query,
                documents=documents,
                top_n=top_n,
            )
        )

    @staticmethod
    def resolve_model_name(selected: "AISelectedModel") -> str | None:
        if (
            isinstance(selected.resolved_model_name, str)
            and selected.resolved_model_name.strip()
        ):
            return selected.resolved_model_name.strip()
        return None

    @staticmethod
    def _register_source(
        source: "AISourceDefinition",
        *,
        api_key: str,
    ) -> None:
        ai_model_client.registry.register(
            source.source_id,
            build_source_adapter(source, api_key=api_key),
        )


ai_model_facade = AIModelFacade()

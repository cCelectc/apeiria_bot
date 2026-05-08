"""Narrow provider invocation boundary for AI models."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Literal

from apeiria.ai.model.runtime.adapter import (
    AIModelEmbeddingRequest,
    AIModelGenerateRequest,
    AIModelRerankRequest,
    AIModelSpeechRequest,
    AIModelStreamRequest,
    AIModelTranscriptionRequest,
)
from apeiria.ai.model.runtime.capabilities import (
    AIModelCallOptions,
    AIModelCallRequirements,
    AIModelCapabilityPlanningError,
)
from apeiria.ai.model.runtime.client import ai_model_client
from apeiria.ai.model.runtime.factory import build_source_adapter
from apeiria.ai.model.runtime.planning import plan_model_call
from apeiria.ai.model.sources.service import ai_source_service

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from apeiria.ai.model.routing.selection import AISelectedModel
    from apeiria.ai.model.runtime.adapter import (
        AIModelCatalogItem,
        AIModelEmbeddingResponse,
        AIModelGenerateResponse,
        AIModelMessage,
        AIModelRerankResponse,
        AIModelSpeechResponse,
        AIModelStreamEvent,
        AIModelToolDefinition,
        AIModelTranscriptionResponse,
    )
    from apeiria.ai.model.sources.models import AISourceDefinition


class ModelInvoker:
    """Provider invocation boundary for selected or explicit model calls."""

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

    async def generate_text(  # noqa: PLR0913
        self,
        selected: "AISelectedModel",
        *,
        prompt: str = "",
        messages: tuple["AIModelMessage", ...] = (),
        tools: tuple["AIModelToolDefinition", ...] = (),
        requirements: AIModelCallRequirements | None = None,
        options: AIModelCallOptions | None = None,
        call_options: dict[str, object] | None = None,
    ) -> "AIModelGenerateResponse | None":
        api_key = ai_source_service.get_source_api_key(selected.source)
        model_name = self.resolve_model_name(selected)
        if not api_key or not model_name:
            return None

        plan = plan_model_call(
            selected=selected,
            messages=messages,
            tools=tools,
            requirements=requirements,
            options=options,
            call_options=call_options,
        )
        if plan.action == "reject":
            raise AIModelCapabilityPlanningError(plan)

        self._register_source(selected.source, api_key=api_key)
        response = await ai_model_client.generate_text(
            AIModelGenerateRequest(
                source_id=selected.source.source_id,
                model_name=model_name,
                prompt=prompt,
                messages=plan.messages,
                tools=plan.tools,
                extra=plan.options,
                options=plan.options,
                degradations=plan.degradations,
            )
        )
        if not plan.degradations:
            return response
        provider_data = dict(response.provider_data or {})
        provider_data["apeiria_degradations"] = [
            {
                "kind": degradation.kind,
                "reason": degradation.reason,
                "detail": degradation.detail,
                "metadata": degradation.metadata,
            }
            for degradation in plan.degradations
        ]
        return replace(response, provider_data=provider_data)

    async def stream_text(  # noqa: PLR0913
        self,
        selected: "AISelectedModel",
        *,
        prompt: str = "",
        messages: tuple["AIModelMessage", ...] = (),
        tools: tuple["AIModelToolDefinition", ...] = (),
        requirements: AIModelCallRequirements | None = None,
        options: AIModelCallOptions | None = None,
        call_options: dict[str, object] | None = None,
    ) -> "AsyncIterator[AIModelStreamEvent]":
        api_key = ai_source_service.get_source_api_key(selected.source)
        model_name = self.resolve_model_name(selected)
        if not api_key or not model_name:
            return

        requested = requirements or AIModelCallRequirements(streaming="required")
        plan = plan_model_call(
            selected=selected,
            messages=messages,
            tools=tools,
            requirements=requested,
            options=options,
            call_options=call_options,
        )
        if plan.action == "reject":
            raise AIModelCapabilityPlanningError(plan)
        if not plan.streaming:
            raise AIModelCapabilityPlanningError(
                plan_model_call(
                    selected=selected,
                    messages=messages,
                    tools=tools,
                    requirements=AIModelCallRequirements(streaming="required"),
                    options=options,
                    call_options=call_options,
                )
            )

        self._register_source(selected.source, api_key=api_key)
        async for event in ai_model_client.stream_text(
            AIModelStreamRequest(
                source_id=selected.source.source_id,
                model_name=model_name,
                prompt=prompt,
                messages=plan.messages,
                tools=plan.tools,
                extra=plan.options,
                options=plan.options,
                degradations=plan.degradations,
            )
        ):
            yield event

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


model_invoker = ModelInvoker()

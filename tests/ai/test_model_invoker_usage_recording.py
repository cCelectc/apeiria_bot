from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from apeiria.ai.model.runtime.capabilities import AIModelCapabilities
from apeiria.db.runtime import database_runtime

UNUSED_MODEL_CALL = "unexpected generation call"

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_model_invoker_records_non_generation_usage_for_summary(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.ai.model.runtime.adapter import (
        AIModelEmbeddingRequest,
        AIModelEmbeddingResponse,
        AIModelRerankRequest,
        AIModelRerankResponse,
        AIModelRerankResultItem,
        AIModelSpeechRequest,
        AIModelSpeechResponse,
        AIModelStreamRequest,
        AIModelTranscriptionRequest,
        AIModelTranscriptionResponse,
    )
    from apeiria.ai.model.runtime.client import ai_model_client
    from apeiria.ai.model.runtime.service import ModelInvoker
    from apeiria.ai.model.sources.models import AISourceDefinition
    from apeiria.ai.token_usage import AIModelUsageRepository

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    original_adapters = dict(ai_model_client.registry.adapters)
    source = AISourceDefinition(
        source_id="source-usage",
        name="Usage Source",
        capability_type="embedding",
        client_type="openai",
        preset_type="openai_compatible_embedding",
        api_base="https://example.invalid/v1",
        adapter_kind="openai_compatible",
    )

    class Adapter:
        async def embed_texts(
            self,
            request: AIModelEmbeddingRequest,
        ) -> AIModelEmbeddingResponse:
            return AIModelEmbeddingResponse(
                source_id=request.source_id,
                model_name=request.model_name,
                vectors=((0.1, 0.2),),
                usage={"prompt_tokens": 3, "total_tokens": 3},
            )

        async def transcribe_audio(
            self,
            request: AIModelTranscriptionRequest,
        ) -> AIModelTranscriptionResponse:
            return AIModelTranscriptionResponse(
                source_id=request.source_id,
                model_name=request.model_name,
                text="hello",
                usage={"prompt_tokens": 4, "total_tokens": 4},
            )

        async def synthesize_speech(
            self,
            request: AIModelSpeechRequest,
        ) -> AIModelSpeechResponse:
            return AIModelSpeechResponse(
                source_id=request.source_id,
                model_name=request.model_name,
                audio_bytes=b"audio",
                response_format=request.response_format,
                usage={"prompt_tokens": 5, "total_tokens": 5},
            )

        async def rerank_documents(
            self,
            request: AIModelRerankRequest,
        ) -> AIModelRerankResponse:
            return AIModelRerankResponse(
                source_id=request.source_id,
                model_name=request.model_name,
                results=(AIModelRerankResultItem(index=0, relevance_score=0.9),),
                usage={"prompt_tokens": 6, "total_tokens": 6},
            )

        async def list_models(self, *, api_key: str | None = None) -> list[Any]:
            del api_key
            return []

        async def generate_text(self, request: object) -> object:
            del request
            raise AssertionError(UNUSED_MODEL_CALL)

        def stream_text(self, request: AIModelStreamRequest) -> object:
            del request
            raise AssertionError(UNUSED_MODEL_CALL)

    monkeypatch.setattr(
        "apeiria.ai.model.runtime.service.build_source_adapter",
        lambda *_, **__: Adapter(),
    )
    try:
        asyncio.run(
            _run_non_generation_calls(
                invoker=ModelInvoker(),
                source=source,
            )
        )
    finally:
        ai_model_client.registry.adapters.clear()
        ai_model_client.registry.adapters.update(original_adapters)

    repository = AIModelUsageRepository()
    summaries = repository.summarize_usage(group_by="operation")
    panel_summaries = repository.summarize_usage(group_by="response_source")
    session_summaries = repository.summarize_usage(
        group_by="response_source",
        session_id="session-1",
    )

    assert {item.group_key: item.total_tokens for item in summaries} == {
        "embedding": 3,
        "rerank": 6,
        "speech_to_text": 4,
        "text_to_speech": 5,
    }
    assert {item.group_key: item.total_tokens for item in panel_summaries} == {
        "embedding": 3,
        "rerank": 6,
        "speech_to_text": 4,
        "text_to_speech": 5,
    }
    assert session_summaries == []


def test_selected_speech_operations_record_usage_for_panel_summary(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.ai.model.routing.models import AIModelProfileDefinition
    from apeiria.ai.model.routing.selection import AISelectedModel
    from apeiria.ai.model.runtime.adapter import (
        AIModelSpeechRequest,
        AIModelSpeechResponse,
        AIModelTranscriptionRequest,
        AIModelTranscriptionResponse,
    )
    from apeiria.ai.model.runtime.client import ai_model_client
    from apeiria.ai.model.runtime.service import ModelInvoker
    from apeiria.ai.model.sources.models import AISourceDefinition
    from apeiria.ai.token_usage import AIModelUsageRepository

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    original_adapters = dict(ai_model_client.registry.adapters)
    stt_selected = AISelectedModel(
        source=AISourceDefinition(
            source_id="source-selected-stt",
            name="Selected STT",
            capability_type="speech_to_text",
            client_type="openai",
            preset_type="openai_compatible_stt",
            api_base="https://example.invalid/v1",
            adapter_kind="openai_compatible",
        ),
        profile=AIModelProfileDefinition(
            profile_id="profile-selected-stt",
            name="Selected STT",
            model_id="model-selected-stt",
            task_class="speech_to_text",
            priority=1,
        ),
        resolved_model_name="stt-selected",
        resolved_capabilities=AIModelCapabilities(
            lanes=frozenset({"speech_to_text"}),
            input_modalities=frozenset({"audio"}),
            output_modalities=frozenset({"text"}),
        ),
    )
    tts_selected = AISelectedModel(
        source=AISourceDefinition(
            source_id="source-selected-tts",
            name="Selected TTS",
            capability_type="text_to_speech",
            client_type="openai",
            preset_type="openai_compatible_tts",
            api_base="https://example.invalid/v1",
            adapter_kind="openai_compatible",
        ),
        profile=AIModelProfileDefinition(
            profile_id="profile-selected-tts",
            name="Selected TTS",
            model_id="model-selected-tts",
            task_class="text_to_speech",
            priority=1,
        ),
        resolved_model_name="tts-selected",
        resolved_capabilities=AIModelCapabilities(
            lanes=frozenset({"text_to_speech"}),
            input_modalities=frozenset({"text"}),
            output_modalities=frozenset({"audio"}),
            supported_options=frozenset({"voice", "response_format"}),
        ),
    )

    class Adapter:
        async def transcribe_audio(
            self,
            request: AIModelTranscriptionRequest,
        ) -> AIModelTranscriptionResponse:
            return AIModelTranscriptionResponse(
                source_id=request.source_id,
                model_name=request.model_name,
                text="hello",
                usage={"prompt_tokens": 7, "total_tokens": 7},
            )

        async def synthesize_speech(
            self,
            request: AIModelSpeechRequest,
        ) -> AIModelSpeechResponse:
            return AIModelSpeechResponse(
                source_id=request.source_id,
                model_name=request.model_name,
                audio_bytes=b"audio",
                response_format=request.response_format,
                usage={"prompt_tokens": 8, "total_tokens": 8},
            )

    monkeypatch.setattr(
        "apeiria.ai.model.runtime.service.build_source_adapter",
        lambda *_, **__: Adapter(),
    )
    monkeypatch.setattr(
        "apeiria.ai.model.runtime.service.ai_source_service.get_source_api_key",
        lambda _: "test-key",
    )
    try:
        invoker = ModelInvoker()
        asyncio.run(
            invoker.transcribe_audio(
                stt_selected,
                audio_bytes=b"wav",
            )
        )
        asyncio.run(
            invoker.synthesize_speech(
                tts_selected,
                text="hello",
            )
        )
    finally:
        ai_model_client.registry.adapters.clear()
        ai_model_client.registry.adapters.update(original_adapters)

    summaries = AIModelUsageRepository().summarize_usage(group_by="response_source")

    assert {item.group_key: item.total_tokens for item in summaries} == {
        "speech_to_text": 7,
        "text_to_speech": 8,
    }


async def _run_non_generation_calls(
    *,
    invoker: object,
    source: object,
) -> None:
    await invoker.embed_texts_for_source(
        source=source,
        api_key="test-key",
        model_name="embedding-test",
        texts=("hello",),
    )
    await invoker.transcribe_audio_for_source(
        source=source,
        api_key="test-key",
        model_name="stt-test",
        audio_bytes=b"wav",
    )
    await invoker.synthesize_speech_for_source(
        source=source,
        api_key="test-key",
        model_name="tts-test",
        text="hello",
    )
    await invoker.rerank_documents_for_source(
        source=source,
        api_key="test-key",
        model_name="rerank-test",
        query="hello",
        documents=("hello world",),
    )

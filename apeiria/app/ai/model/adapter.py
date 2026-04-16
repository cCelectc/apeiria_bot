"""Adapter contracts for AI model execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class AIModelToolDefinition:
    """One function-calling tool definition exposed to a model source adapter."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class AIModelToolCall:
    """One tool call returned by a model source adapter."""

    tool_call_id: str
    name: str
    arguments: dict[str, Any]


AIModelMessageRole = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class AIModelMessage:
    """One message in a chat conversation.

    - ``role="system"`` — system-level instructions (persona, rules).
    - ``role="user"`` — user turn.
    - ``role="assistant"`` — assistant turn, may carry ``tool_calls``.
    - ``role="tool"`` — tool result, must have ``tool_call_id``.
    """

    role: AIModelMessageRole
    content: str
    tool_call_id: str | None = None
    tool_calls: tuple[AIModelToolCall, ...] = ()


@dataclass(frozen=True)
class AIModelCatalogItem:
    """One source-reported model catalog item."""

    id: str
    name: str


@dataclass(frozen=True)
class AIModelGenerateRequest:
    """Unified text generation request for Apeiria AI services.

    When ``messages`` is non-empty, adapters use it directly (chat mode).
    When empty, ``prompt`` is wrapped as a single user message (legacy mode).
    """

    source_id: str
    model_name: str
    prompt: str = ""
    messages: tuple[AIModelMessage, ...] = ()
    temperature: float | None = None
    max_tokens: int | None = None
    tools: tuple[AIModelToolDefinition, ...] = ()
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelGenerateResponse:
    """Unified text generation response for Apeiria AI services."""

    source_id: str
    model_name: str
    content: str
    tool_calls: tuple[AIModelToolCall, ...] = ()
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelEmbeddingRequest:
    """Unified embedding request for Apeiria AI services."""

    source_id: str
    model_name: str
    texts: tuple[str, ...]
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelEmbeddingResponse:
    """Unified embedding response for Apeiria AI services."""

    source_id: str
    model_name: str
    vectors: tuple[tuple[float, ...], ...]
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelTranscriptionRequest:
    """Unified speech-to-text request for Apeiria AI services."""

    source_id: str
    model_name: str
    audio_bytes: bytes
    file_name: str = "sample.wav"
    mime_type: str = "audio/wav"
    language: str | None = None
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelTranscriptionResponse:
    """Unified speech-to-text response for Apeiria AI services."""

    source_id: str
    model_name: str
    text: str
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelSpeechRequest:
    """Unified text-to-speech request for Apeiria AI services."""

    source_id: str
    model_name: str
    text: str
    voice: str = "alloy"
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "wav"
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelSpeechResponse:
    """Unified text-to-speech response for Apeiria AI services."""

    source_id: str
    model_name: str
    audio_bytes: bytes
    response_format: str
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelRerankResultItem:
    """One rerank-scored document result."""

    index: int
    relevance_score: float
    document: str | None = None


@dataclass(frozen=True)
class AIModelRerankRequest:
    """Unified rerank request for Apeiria AI services."""

    source_id: str
    model_name: str
    query: str
    documents: tuple[str, ...]
    top_n: int = 3
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelRerankResponse:
    """Unified rerank response for Apeiria AI services."""

    source_id: str
    model_name: str
    results: tuple[AIModelRerankResultItem, ...]
    raw: dict[str, Any] | None = None


class AIModelAdapter(Protocol):
    """Source adapter protocol for Apeiria model execution."""

    async def list_models(
        self,
        *,
        api_key: str | None = None,
    ) -> list[AIModelCatalogItem]: ...

    async def generate_text(
        self,
        request: AIModelGenerateRequest,
    ) -> AIModelGenerateResponse: ...

    async def embed_texts(
        self,
        request: AIModelEmbeddingRequest,
    ) -> AIModelEmbeddingResponse: ...

    async def transcribe_audio(
        self,
        request: AIModelTranscriptionRequest,
    ) -> AIModelTranscriptionResponse: ...

    async def synthesize_speech(
        self,
        request: AIModelSpeechRequest,
    ) -> AIModelSpeechResponse: ...

    async def rerank_documents(
        self,
        request: AIModelRerankRequest,
    ) -> AIModelRerankResponse: ...
